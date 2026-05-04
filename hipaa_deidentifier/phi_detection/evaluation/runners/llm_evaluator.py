"""Annotation-free LLM evaluation runner."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hipaa_deidentifier.models.phi_entity import PHIEntity
from hipaa_deidentifier.phi_detection.clinical_patterns import (
    detect_ages_over_89,
    detect_long_numeric_ids,
    detect_section_headers,
)

from ..evaluation_config import EvaluationConfig

if TYPE_CHECKING:
    from ..judges.lm_studio_judge import LMStudioJudge
    from ..judges.openai_judge import OpenAIJudge

logger = logging.getLogger(__name__)


@dataclass
class _GoldSpan:
    """Ground-truth span resolved from a single LLM-identified expected entity.

    The LLM returns expected entities as {text, category} with no character
    positions.  _resolve_gold_spans() locates every occurrence of each entity
    text in the document and creates one _GoldSpan per occurrence, because the
    same name or date may appear multiple times and each occurrence is an
    independent PHI instance that must be redacted.

    Attributes:
        start: Inclusive start offset in the document string.
        end: Exclusive end offset in the document string.
        entity_type: HIPAA category as returned by the LLM (e.g. "NAME").
        text: The matched document substring (may differ in case from the
              LLM's entity text due to case-insensitive matching).
    """

    start: int
    end: int
    entity_type: str
    text: str


_DETECTOR_LABELS: Dict[str, str] = {
    "hf": "HFIdentifier (obi/deid_bert_i2b2)",
    "presidio": "PresidioIdentifier + spaCy (en_core_web_lg)",
    "heuristics": "Clinical Heuristics (section_headers + ages + numeric_ids)",
    "pipeline": "Full Pipeline (HF + Presidio + Heuristics, merged)",
    "pipeline_filtered": "Full Pipeline + FP Guardrail (post-filter)",
}

_LLM_SYSTEM_PROMPT = """You are a HIPAA Safe Harbor evaluation specialist (45 CFR §164.514(b)).

Your task: identify ONLY the 18 HIPAA Safe Harbor identifiers in the document.
DO NOT label clinical content (medications, diagnoses, vital signs, lab results,
allergies, procedures, conditions, symptoms, BMI, weight, dosage values, A1c values,
diagnosis years, scored assessments, or other medical facts) as PHI.
DO NOT use OTHER_ID as a catch-all — only use it for an explicit labeled identifier
(e.g. "Badge #: 45678", "License: RN-98765") that does not fit any other category.

The ONLY valid entity types you may use in the `category` field are:
  NAME, DATE, PHONE_NUMBER, FAX_NUMBER, EMAIL_ADDRESS, US_SSN, MRN,
  ACCOUNT_NUMBER, CERTIFICATE_NUMBER, VIN, DEVICE_ID, URL, IP_ADDRESS,
  LOCATION, AGE_OVER_89, PROVIDER_NAME, ORGANIZATION, OTHER_ID

HIPAA date rule: ALL dates (with month or day) are PHI — including admission dates,
discharge dates, appointment dates, procedure dates, lab dates, medication dates,
and dates of birth. Year-only values (e.g. "2015") are NOT PHI.

HIPAA age rule: ONLY label AGE_OVER_89 when the document explicitly states the
patient is 90 or older, OR when a birth year implies age > 89. A patient described
as "45-year-old", "62-year-old", "78-year-old" — any age 89 or under — is NOT PHI.
Do NOT label every age mention as AGE_OVER_89.

Return only JSON matching the provided schema. Do not include markdown."""


class LLMEvaluator:
    """Run PHI detectors and evaluate their output with a local LLM judge."""

    def __init__(
        self,
        document_path: str,
        detectors: str,
        config: EvaluationConfig,
        use_judge: bool = True,
    ) -> None:
        self.document_path = Path(document_path)
        self.detectors = self._parse_detectors(detectors)
        self.config = config
        self.use_judge = use_judge
        self._text = ""
        # Populated by _run_detectors(); used by _compute_span_metrics()
        # after the LLM response arrives so we can score each detector
        # against the LLM-derived gold spans without re-running detection.
        self._raw_entities: Dict[str, List[PHIEntity]] = {}
        self._judge: Optional["LMStudioJudge | OpenAIJudge"] = None
        if use_judge:
            if config.active_backend == "openai":
                from ..judges.openai_judge import OpenAIJudge

                oai = config.openai_api
                self._judge = OpenAIJudge(
                    model=oai.model,
                    api_key_env=oai.api_key_env,
                    timeout_seconds=oai.timeout_seconds,
                    temperature=oai.temperature,
                    max_tokens=oai.max_tokens,
                )
                logger.info("Judge backend: OpenAI (%s)", oai.model)
            else:
                from ..judges.lm_studio_judge import LMStudioJudge

                self._judge = LMStudioJudge(
                    base_url=config.lm_studio.base_url,
                    model=config.lm_studio.model,
                )
                logger.info("Judge backend: LM Studio (%s)", config.lm_studio.model)

    def run(self) -> dict[str, Any]:
        if not self.document_path.exists():
            raise FileNotFoundError(f"Document not found: {self.document_path}")

        self._text = self.document_path.read_text(encoding="utf-8")
        detector_results = self._run_detectors()

        result: dict[str, Any] = {
            "evaluation_mode": "llm",
            "document": self.document_path.stem,
            "document_path": str(self.document_path),
            "evaluation_config": self.config.to_dict(),
            "detector_entities": detector_results,
            "llm_expected_entities": [],
            "llm_judgment": None,
            "llm_status": "ok",
            "llm_error_message": None,
        }

        if not self.use_judge:
            result["llm_status"] = "error"
            result["llm_error_message"] = "LLM judge disabled by --no-judge."
            return result

        prompt = self._build_prompt(detector_results)
        assert self._judge is not None

        # Route config kwargs to whichever backend is active.
        # Both judges share the same generate_json signature; base_url is a
        # no-op for the OpenAI judge (it uses the SDK endpoint internally).
        if self.config.active_backend == "openai":
            _cfg = self.config.openai_api
            _judge_kwargs: dict[str, str | int | float] = {
                "model": str(_cfg.model),
                "timeout_seconds": float(_cfg.timeout_seconds),
                "max_tokens": int(_cfg.max_tokens),
                "temperature": float(_cfg.temperature),
            }
        else:
            _cfg = self.config.lm_studio  # type: ignore[assignment]
            _judge_kwargs = {
                "base_url": str(_cfg.base_url),
                "model": str(_cfg.model),
                "timeout_seconds": float(_cfg.timeout_seconds),
                "max_tokens": int(_cfg.max_tokens),
                "temperature": float(_cfg.temperature),
            }

        response = self._judge.generate_json(
            prompt,
            self._build_response_schema(),
            system_prompt=_LLM_SYSTEM_PROMPT,
            use_response_format=self.config.llm_judge.use_response_format,
            **_judge_kwargs,  # type: ignore[arg-type]
        )

        result["llm_status"] = response["status"]
        result["llm_error_message"] = response["error_message"]
        if self.config.reports.include_llm_raw_response:
            result["llm_raw_response"] = response["raw_response"]

        if response["status"] == "ok":
            data = response["data"] or {}
            result["llm_expected_entities"] = data.get("expected_entities", [])
            result["llm_judgment"] = data.get("judgment", {})
            # Resolve entity texts to character positions and compute
            # deterministic token-level and span-level metrics for every
            # detector that ran successfully.
            gold_spans = self._resolve_gold_spans(result["llm_expected_entities"])
            result["llm_gold_spans_count"] = len(gold_spans)
            result["span_metrics"] = self._compute_span_metrics(gold_spans)

        return result

    def _run_detectors(self) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for detector in self.detectors:
            label = _DETECTOR_LABELS[detector]
            try:
                if detector == "hf":
                    entities = self._run_hf_detector()
                elif detector == "presidio":
                    entities = self._run_presidio_detector()
                elif detector == "heuristics":
                    entities = self._run_heuristics_detector()
                elif detector == "pipeline_filtered":
                    entities = self._run_pipeline_filtered_detector()
                else:
                    entities = self._run_pipeline_detector()

                self._raw_entities[label] = entities
                results[label] = {
                    "status": "ok",
                    "error_message": None,
                    "entities": [self._serialize_entity(e) for e in entities],
                }
                logger.info("%s detected %d entities", label, len(entities))

            except Exception as exc:
                logger.error("%s failed: %s", label, exc)
                results[label] = {
                    "status": "error",
                    "error_message": str(exc),
                    "entities": [],
                }

        return results

    def _run_hf_detector(self) -> List[PHIEntity]:
        from config.config import config as global_config
        from hipaa_deidentifier.phi_detection.identifier.huggingface_model_identifier import (
            HFIdentifier,
        )

        cfg = global_config.get_settings()
        hf_model = cfg.get("models", {}).get("huggingface", "obi/deid_bert_i2b2")
        device = cfg.get("models", {}).get("device", -1)
        return HFIdentifier(hf_model=hf_model, device=device, config=cfg).detect(
            self._text
        )

    def _run_presidio_detector(self) -> List[PHIEntity]:
        from config.config import config as global_config
        from hipaa_deidentifier.phi_detection.identifier.presidio_identifier import (
            PresidioIdentifier,
        )

        cfg = global_config.get_settings()
        identifier = PresidioIdentifier(config=cfg)
        entities = identifier.detect(self._text)
        entities.extend(identifier.detect_with_header_patterns(self._text))
        return entities

    def _run_heuristics_detector(self) -> List[PHIEntity]:
        entities: List[PHIEntity] = []
        entities.extend(detect_section_headers(self._text))
        entities.extend(detect_ages_over_89(self._text))
        entities.extend(detect_long_numeric_ids(self._text, existing_entities=entities))
        return entities

    def _run_pipeline_detector(self) -> List[PHIEntity]:
        from hipaa_deidentifier.pipeline_orchestrator import HIPAAPipelineOrchestrator

        orchestrator = HIPAAPipelineOrchestrator()
        return orchestrator._detect_phi_entities(self._text)

    def _run_pipeline_filtered_detector(self) -> List[PHIEntity]:
        from hipaa_deidentifier.pipeline_orchestrator import HIPAAPipelineOrchestrator

        orchestrator = HIPAAPipelineOrchestrator()
        entities = orchestrator._detect_phi_entities(self._text)
        return orchestrator.fp_guardrail.filter(entities, self._text)

    def _build_prompt(self, detector_results: dict[str, dict[str, Any]]) -> str:
        max_expected = self.config.llm_judge.max_expected_entities
        threshold = self.config.llm_judge.coverage_pass_threshold
        return (
            "Evaluate HIPAA Safe Harbor PHI detection for this document.\n\n"
            f"Coverage pass threshold: {threshold:.2f}\n"
            f"Maximum expected entities to list: {max_expected}\n\n"
            "Document text:\n"
            "---\n"
            f"{self._text}\n"
            "---\n\n"
            "Detector outputs JSON:\n"
            f"{json.dumps(detector_results, indent=2, ensure_ascii=False)}\n\n"
            "Instructions:\n"
            "1. Identify ALL HIPAA Safe Harbor PHI entities from the document — use ONLY the allowed category names from the system prompt.\n"
            "   - Include ALL dates that contain a month or day (admission, discharge, procedure, lab, medication, appointment, DOB).\n"
            "   - Include ALL person names (patient and provider/physician names).\n"
            "   - Do NOT label medications, diagnoses, vital signs, lab values, allergies, or other clinical facts.\n"
            "2. Judge detector coverage against those expected PHI entities.\n"
            "3. Treat a detector entity as covering expected PHI when it captures the same PHI value or a materially equivalent substring.\n"
            "4. Mark risky misses clearly, especially names, MRNs, dates, account numbers, ages over 89, locations, SSNs, phones, emails, URLs, device IDs, and other identifiers.\n"
            "5. Return only JSON matching the schema."
        )

    @staticmethod
    def _serialize_entity(entity: PHIEntity) -> dict[str, Any]:
        return {
            "text": entity.text,
            "category": entity.category,
            "start": entity.start,
            "end": entity.end,
            "confidence": entity.confidence,
            "source": entity.source,
        }

    def _resolve_gold_spans(
        self, expected_entities: List[Dict[str, Any]]
    ) -> List[_GoldSpan]:
        """Resolve LLM-identified entity texts to character spans in the document.

        For each expected entity the LLM returned, find every occurrence of
        that text in the document using case-insensitive exact matching.  All
        occurrences become separate gold spans because repeated names/dates are
        each independently a PHI instance.

        Deduplication: if the LLM lists the same (text, category) pair more
        than once we only search once, so gold span counts are never inflated
        by duplicate LLM output.

        Args:
            expected_entities: List of dicts with at least "text" and
                               "category" keys, as returned by the LLM.

        Returns:
            Flat list of _GoldSpan objects ordered by occurrence in the text.
        """
        seen: set[tuple[str, str]] = set()
        spans: List[_GoldSpan] = []

        for entity in expected_entities:
            raw_text = (entity.get("text") or "").strip()
            entity_type = (entity.get("category") or "").strip().upper()
            if not raw_text or not entity_type:
                continue

            dedup_key = (raw_text.lower(), entity_type)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            try:
                pattern = re.compile(re.escape(raw_text), re.IGNORECASE)
                for match in pattern.finditer(self._text):
                    spans.append(
                        _GoldSpan(
                            start=match.start(),
                            end=match.end(),
                            entity_type=entity_type,
                            text=match.group(),
                        )
                    )
            except re.error:
                logger.warning(
                    "Could not compile regex for entity text: %r — skipped", raw_text
                )

        logger.info(
            "Resolved %d gold spans from %d expected entities (%d unique)",
            len(spans),
            len(expected_entities),
            len(seen),
        )
        return spans

    def _compute_span_metrics(self, gold_spans: List[_GoldSpan]) -> Dict[str, Any]:
        """Compute token-level and span-level metrics for every detector.

        Uses _resolve_gold_spans() output as ground truth.  Results are
        returned as a plain serialisable dict so they can be embedded directly
        in the JSON report without further processing.

        Two complementary modes are computed and reported side-by-side:

        Token-level (primary):
            Every character position is a unit.  A detector that catches
            "John" when the gold is "John Smith" still earns partial credit
            for the four characters it did cover.  This is the right primary
            metric for HIPAA because any leaked character is a risk.

        Span-level (secondary / strict):
            A predicted span must overlap ≥50% of a gold span to count as a
            true positive.  No partial credit — either the span is covered or
            it is not.  Used for HIPAA audit reporting where you need a
            binary "was this entity fully redacted?" answer.

        Args:
            gold_spans: List of _GoldSpan objects from _resolve_gold_spans().

        Returns:
            Dict keyed by detector label → {overall: {...}, per_type: {...}}.
        """
        from ..metrics.span_metrics import compute_per_detector_metrics

        result: Dict[str, Any] = {}

        for label, entities in self._raw_entities.items():
            token_m = compute_per_detector_metrics(
                label, entities, gold_spans, self._text, mode="token"
            )
            span_m = compute_per_detector_metrics(
                label, entities, gold_spans, self._text, mode="span"
            )

            # Build per-type table — union of types seen in token and span modes
            all_types = sorted(set(token_m.per_type) | set(span_m.per_type))
            per_type_out: Dict[str, Any] = {}
            for etype in all_types:
                tm = token_m.per_type.get(etype)
                sm = span_m.per_type.get(etype)
                per_type_out[etype] = {
                    "token_precision": round(tm.precision, 4) if tm else None,
                    "token_recall": round(tm.recall, 4) if tm else None,
                    "token_f1": round(tm.f1, 4) if tm else None,
                    "token_false_negative_rate": (
                        round(tm.false_negative_rate, 4) if tm else None
                    ),
                    "span_precision": round(sm.precision, 4) if sm else None,
                    "span_recall": round(sm.recall, 4) if sm else None,
                    "span_f1": round(sm.f1, 4) if sm else None,
                }

            result[label] = {
                "overall": {
                    "token_precision": round(token_m.precision, 4),
                    "token_recall": round(token_m.recall, 4),
                    "token_f1": round(token_m.f1, 4),
                    "token_false_negative_rate": round(token_m.false_negative_rate, 4),
                    "span_precision": round(span_m.precision, 4),
                    "span_recall": round(span_m.recall, 4),
                    "span_f1": round(span_m.f1, 4),
                },
                "per_type": per_type_out,
            }
            logger.info(
                "[%s] token recall=%.3f span recall=%.3f",
                label,
                token_m.recall,
                span_m.recall,
            )

        return result

    @staticmethod
    def _parse_detectors(detectors_str: str) -> List[str]:
        valid = {"hf", "presidio", "heuristics", "pipeline", "pipeline_filtered"}
        if detectors_str.strip().lower() == "all":
            return ["hf", "presidio", "heuristics", "pipeline", "pipeline_filtered"]

        requested = [d.strip().lower() for d in detectors_str.split(",") if d.strip()]
        return [d for d in requested if d in valid]

    @staticmethod
    def _build_response_schema() -> dict[str, Any]:
        entity_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "text": {"type": "string"},
                "category": {"type": "string"},
                "evidence": {"type": "string"},
                "severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                },
                "rationale": {"type": "string"},
            },
            "required": ["text", "category", "evidence", "severity", "rationale"],
        }
        return {
            "name": "hipaa_phi_evaluation",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "document_summary": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "expected_entities": {
                        "type": "array",
                        "items": entity_schema,
                    },
                    "judgment": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "overall_pass": {"type": "boolean"},
                            "coverage_score": {"type": "number"},
                            "missed_entities": {
                                "type": "array",
                                "items": entity_schema,
                            },
                            "false_positives": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "text": {"type": "string"},
                                        "category": {"type": "string"},
                                        "detector": {"type": "string"},
                                        "rationale": {"type": "string"},
                                    },
                                    "required": [
                                        "text",
                                        "category",
                                        "detector",
                                        "rationale",
                                    ],
                                },
                            },
                            "category_mismatches": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "text": {"type": "string"},
                                        "expected_category": {"type": "string"},
                                        "detected_category": {"type": "string"},
                                        "detector": {"type": "string"},
                                        "rationale": {"type": "string"},
                                    },
                                    "required": [
                                        "text",
                                        "expected_category",
                                        "detected_category",
                                        "detector",
                                        "rationale",
                                    ],
                                },
                            },
                            "risk_summary": {"type": "string"},
                            "recommendations": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "overall_pass",
                            "coverage_score",
                            "missed_entities",
                            "false_positives",
                            "category_mismatches",
                            "risk_summary",
                            "recommendations",
                        ],
                    },
                },
                "required": [
                    "document_summary",
                    "confidence",
                    "expected_entities",
                    "judgment",
                ],
            },
        }
