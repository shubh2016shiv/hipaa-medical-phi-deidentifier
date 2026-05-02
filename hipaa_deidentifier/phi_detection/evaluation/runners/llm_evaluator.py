"""Annotation-free LLM evaluation runner."""

from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)

_DETECTOR_LABELS: Dict[str, str] = {
    "hf": "HFIdentifier (obi/deid_bert_i2b2)",
    "presidio": "PresidioIdentifier + spaCy (en_core_web_lg)",
    "heuristics": "Clinical Heuristics (section_headers + ages + numeric_ids)",
    "pipeline": "Full Pipeline (HF + Presidio + Heuristics, merged)",
}

_LLM_SYSTEM_PROMPT = """You are a HIPAA Safe Harbor evaluation specialist.
You will receive a clinical document and PHI detector outputs. First identify
the expected HIPAA Safe Harbor PHI entities in the document, then judge whether
the detector outputs cover those entities. Return only JSON that matches the
provided schema. Do not include markdown."""


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
        self._judge: Optional["LMStudioJudge"] = None
        if use_judge:
            from ..judges.lm_studio_judge import LMStudioJudge
            self._judge = LMStudioJudge(
                base_url=config.lm_studio.base_url,
                model=config.lm_studio.model,
            )

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
        response = self._judge.generate_json(
            prompt,
            self._build_response_schema(),
            system_prompt=_LLM_SYSTEM_PROMPT,
            base_url=self.config.lm_studio.base_url,
            model=self.config.lm_studio.model,
            timeout_seconds=self.config.lm_studio.timeout_seconds,
            max_tokens=self.config.lm_studio.max_tokens,
            temperature=self.config.lm_studio.temperature,
            use_response_format=self.config.llm_judge.use_response_format,
        )

        result["llm_status"] = response["status"]
        result["llm_error_message"] = response["error_message"]
        if self.config.reports.include_llm_raw_response:
            result["llm_raw_response"] = response["raw_response"]

        if response["status"] == "ok":
            data = response["data"] or {}
            result["llm_expected_entities"] = data.get("expected_entities", [])
            result["llm_judgment"] = data.get("judgment", {})

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
                else:
                    entities = self._run_pipeline_detector()

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
        from hipaa_deidentifier.phi_detection.identifier.huggingface_model_identifier import HFIdentifier

        cfg = global_config.get_settings()
        hf_model = cfg.get("models", {}).get("huggingface", "obi/deid_bert_i2b2")
        device = cfg.get("models", {}).get("device", -1)
        return HFIdentifier(hf_model=hf_model, device=device, config=cfg).detect(self._text)

    def _run_presidio_detector(self) -> List[PHIEntity]:
        from config.config import config as global_config
        from hipaa_deidentifier.phi_detection.identifier.presidio_identifier import PresidioIdentifier

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
            "1. Identify expected HIPAA Safe Harbor PHI entities from the document.\n"
            "2. Judge detector coverage against the expected PHI entities.\n"
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

    @staticmethod
    def _parse_detectors(detectors_str: str) -> List[str]:
        valid = {"hf", "presidio", "heuristics", "pipeline"}
        if detectors_str.strip().lower() == "all":
            return ["hf", "presidio", "heuristics", "pipeline"]

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
                "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
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
                            "missed_entities": {"type": "array", "items": entity_schema},
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
                                    "required": ["text", "category", "detector", "rationale"],
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
