"""
Detector Evaluator — Isolated Per-Detector PHI Detection Evaluation
=====================================================================

Runs each PHI detector (HFIdentifier, PresidioIdentifier, clinical heuristics)
in isolation against a single clinical document, then scores each detector
against the pre-built ground truth annotations.

Architecture:
-------------
    ┌─────────────────────┐
    │  DetectorEvaluator  │
    │  (this module)      │
    └──────────┬──────────┘
               │  runs independently
    ┌──────────▼──────────────────────────────────────┐
    │  HFIdentifier.detect()         → hf_entities    │
    │  PresidioIdentifier.detect()   → presidio_ent.  │
    │  detect_section_headers()  \                    │
    │  detect_ages_over_89()      }  → heuristic_ent. │
    │  detect_long_numeric_ids() /                    │
    └──────────┬──────────────────────────────────────┘
               │  scored by
    ┌──────────▼──────────┐
    │  span_metrics.py    │ → DetectorMetrics
    └──────────┬──────────┘
               │  failed entities sent to
    ┌──────────▼──────────┐
    │  HIPAACoverageMetric│ → LMStudioJudge (if enabled)
    └─────────────────────┘

Dependencies:
    - hipaa_deidentifier/phi_detection/identifier/  (detectors under test)
    - hipaa_deidentifier/phi_detection/clinical_patterns.py
    - evaluation/ground_truth/annotation_schema.py
    - evaluation/metrics/span_metrics.py
    - evaluation/metrics/hipaa_coverage_metric.py

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from deepeval.test_case import LLMTestCase

from hipaa_deidentifier.models.phi_entity import PHIEntity
from hipaa_deidentifier.phi_detection.clinical_patterns import (
    detect_clinical_phi,
)

from ..ground_truth.annotation_schema import AnnotatedDocument
from ..metrics.hipaa_coverage_metric import HIPAACoverageMetric
from ..metrics.span_metrics import DetectorMetrics, compute_per_detector_metrics

if TYPE_CHECKING:
    from ..judges.lm_studio_judge import LMStudioJudge

logger = logging.getLogger(__name__)

# Mapping from CLI names to internal detector labels
_DETECTOR_LABELS: Dict[str, str] = {
    "hf": "HFIdentifier (obi/deid_bert_i2b2)",
    "presidio": "PresidioIdentifier + spaCy (en_core_web_lg)",
    "heuristics": "Clinical Heuristics (detect_clinical_phi suite)",
}


class DetectorEvaluator:
    """Runs each PHI detector in isolation and scores against ground truth.

    Each detector is initialised independently so that its performance is
    not influenced by the other detectors' output. This is the key
    difference from PipelineEvaluator, which runs the full merged pipeline.

    Attributes:
        document_path: Path to the clinical note being evaluated.
        detectors: Comma-separated list of detectors or 'all'.
        use_judge: Whether to invoke the LM Studio judge on failures.

    Example:
        >>> evaluator = DetectorEvaluator(
        ...     document_path="data/Long-term and Supportive Care/home_health_assessment_patient_01.txt",
        ...     detectors="all",
        ...     use_judge=True,
        ... )
        >>> results = evaluator.run()
        >>> for name, metrics in results.items():
        ...     print(f"{name}: Recall={metrics.recall:.2%}")
    """

    def __init__(
        self,
        document_path: str,
        detectors: str = "all",
        use_judge: bool = True,
        annotation_dir: Optional[str] = None,
    ) -> None:
        """Initialise the detector evaluator.

        Args:
            document_path: Path to the clinical note file.
            detectors: Comma-separated detector names or 'all'.
            use_judge: If True, call LM Studio judge on failures.
            annotation_dir: Override directory for annotation JSON files.

        Example:
            >>> ev = DetectorEvaluator("data/.../note.txt", detectors="hf,presidio")
        """
        self.document_path = Path(document_path)
        self.use_judge = use_judge
        self.annotation_dir = annotation_dir

        self._requested_detectors = self._parse_detectors(detectors)
        self._text: str = ""
        self._annotated_doc: Optional[AnnotatedDocument] = None
        self._judge: Optional["LMStudioJudge"] = None
        if use_judge:
            from ..judges.lm_studio_judge import LMStudioJudge
            self._judge = LMStudioJudge()

        logger.info(
            "DetectorEvaluator initialised: doc=%s detectors=%s judge=%s",
            self.document_path.name,
            self._requested_detectors,
            "enabled" if use_judge else "disabled",
        )

    # -----------------------------------------------------------------------
    # Public interface
    # -----------------------------------------------------------------------

    def run(self) -> Dict[str, DetectorMetrics]:
        """Execute the evaluation and return per-detector metrics.

        Returns:
            Dict mapping detector label → DetectorMetrics.

        Raises:
            FileNotFoundError: If the document or annotation file is not found.

        Example:
            >>> results = evaluator.run()
            >>> print(results["HFIdentifier (obi/deid_bert_i2b2)"].recall)
        """
        self._load_document_and_annotations()
        results: Dict[str, DetectorMetrics] = {}

        if "hf" in self._requested_detectors:
            results[_DETECTOR_LABELS["hf"]] = self._run_hf_detector()

        if "presidio" in self._requested_detectors:
            results[_DETECTOR_LABELS["presidio"]] = self._run_presidio_detector()

        if "heuristics" in self._requested_detectors:
            results[_DETECTOR_LABELS["heuristics"]] = self._run_heuristics_detector()

        logger.info(
            "DetectorEvaluator complete: %d detectors evaluated", len(results)
        )
        return results

    # -----------------------------------------------------------------------
    # Document loading
    # -----------------------------------------------------------------------

    def _load_document_and_annotations(self) -> None:
        """Load the document text and find the matching annotation file.

        Raises:
            FileNotFoundError: If the document or annotation is not found.
        """
        if not self.document_path.exists():
            raise FileNotFoundError(
                f"Document not found: {self.document_path}. "
                "Provide a path relative to the project root or an absolute path."
            )

        self._text = self.document_path.read_text(encoding="utf-8")
        logger.info(
            "Loaded document: %s (%d chars)", self.document_path.name, len(self._text)
        )

        self._annotated_doc = AnnotatedDocument.find_annotation_for_document(
            document_path=self.document_path,
            annotation_dir=self.annotation_dir,
        )
        logger.info(
            "Loaded annotation: %d PHI spans", len(self._annotated_doc.annotations)
        )

    # -----------------------------------------------------------------------
    # Per-detector runners
    # -----------------------------------------------------------------------

    def _run_hf_detector(self) -> DetectorMetrics:
        """Run HFIdentifier in isolation and compute metrics.

        Returns:
            DetectorMetrics for the HF model alone.
        """
        logger.info("Running HFIdentifier...")
        label = _DETECTOR_LABELS["hf"]

        try:
            from config.config import config as global_config
            from hipaa_deidentifier.phi_detection.identifier.huggingface_model_identifier import HFIdentifier
            cfg = global_config.get_settings()
            hf_model = cfg.get("models", {}).get("huggingface", "obi/deid_bert_i2b2")
            device = cfg.get("models", {}).get("device", -1)

            identifier = HFIdentifier(hf_model=hf_model, device=device, config=cfg)
            entities: List[PHIEntity] = identifier.detect(self._text)
            logger.info("HFIdentifier detected %d entities", len(entities))

        except Exception as exc:
            logger.error("HFIdentifier failed: %s", exc)
            return self._build_error_metrics(label, exc)

        return self._score_entities(label, entities)

    def _run_presidio_detector(self) -> DetectorMetrics:
        """Run PresidioIdentifier (with spaCy) in isolation and compute metrics.

        Returns:
            DetectorMetrics for Presidio + spaCy alone.
        """
        logger.info("Running PresidioIdentifier + spaCy...")
        label = _DETECTOR_LABELS["presidio"]

        try:
            from config.config import config as global_config
            from hipaa_deidentifier.phi_detection.identifier.presidio_identifier import PresidioIdentifier
            cfg = global_config.get_settings()

            identifier = PresidioIdentifier(config=cfg)
            entities: List[PHIEntity] = identifier.detect(self._text)
            # Also run header patterns (these are part of Presidio's detect_with_header_patterns)
            header_entities = identifier.detect_with_header_patterns(self._text)
            entities.extend(header_entities)
            logger.info(
                "PresidioIdentifier detected %d entities (%d header)",
                len(entities) - len(header_entities),
                len(header_entities),
            )

        except Exception as exc:
            logger.error("PresidioIdentifier failed: %s", exc)
            return self._build_error_metrics(label, exc)

        return self._score_entities(label, entities)

    def _run_heuristics_detector(self) -> DetectorMetrics:
        """Run clinical heuristic detectors in isolation and compute metrics.

    Includes the same clinical heuristic suite used by the broader heuristic
        module: section headers, initials/nicknames, facility names,
        relatives/contacts, ages over 89, and long numeric IDs.

        Returns:
            DetectorMetrics for clinical heuristics alone.
        """
        logger.info("Running clinical heuristics...")
        label = _DETECTOR_LABELS["heuristics"]

        try:
            entities: List[PHIEntity] = detect_clinical_phi(self._text)
            logger.info("Heuristics detected %d entities", len(entities))

        except Exception as exc:
            logger.error("Heuristics detection failed: %s", exc)
            return self._build_error_metrics(label, exc)

        return self._score_entities(label, entities)

    # -----------------------------------------------------------------------
    # Scoring
    # -----------------------------------------------------------------------

    def _score_entities(
        self,
        detector_name: str,
        entities: List[PHIEntity],
    ) -> DetectorMetrics:
        """Score predicted entities against ground truth, then run coverage metric.

        Args:
            detector_name: Human-readable detector label.
            entities: Predicted PHIEntity list from the detector.

        Returns:
            DetectorMetrics with optional judge analysis attached to reason.
        """
        assert self._annotated_doc is not None, "_load_document_and_annotations must run first"

        # Primary: token-level metrics
        token_metrics = compute_per_detector_metrics(
            detector_name=detector_name,
            predicted_entities=entities,
            gold_spans=self._annotated_doc.annotations,
            text=self._text,
            mode="token",
        )

        # Secondary: span-level metrics (stored in per_type as "_span" suffix)
        span_metrics = compute_per_detector_metrics(
            detector_name=detector_name,
            predicted_entities=entities,
            gold_spans=self._annotated_doc.annotations,
            text=self._text,
            mode="span",
        )

        # Attach span-level per_type alongside token-level
        for etype, sm in span_metrics.per_type.items():
            token_metrics.per_type[f"{etype}_span"] = sm
        token_metrics.per_type["_ALL_span"] = span_metrics.overall

        # HIPAA coverage metric (calls judge if enabled)
        coverage_metric = HIPAACoverageMetric(
            threshold=0.95, judge=self._judge
        )
        dummy_test_case = LLMTestCase(
            input=self.document_path.name,
            actual_output=f"detected {len(entities)} entities",
        )
        coverage_metric.measure(dummy_test_case, token_metrics, self._annotated_doc)

        logger.info(
            "[%s] Recall=%.2f%% Precision=%.2f%% F1=%.2f%% | "
            "HIPAA Coverage: %s",
            detector_name,
            token_metrics.recall * 100,
            token_metrics.precision * 100,
            token_metrics.f1 * 100,
            "PASS" if coverage_metric.is_successful() else "FAIL",
        )

        # Attach coverage metric result to metrics object as metadata
        token_metrics.hipaa_coverage_score = coverage_metric.score      # type: ignore[attr-defined]
        token_metrics.hipaa_coverage_pass = coverage_metric.is_successful()  # type: ignore[attr-defined]
        token_metrics.hipaa_coverage_reason = coverage_metric.reason    # type: ignore[attr-defined]

        return token_metrics

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _build_error_metrics(detector_name: str, exc: Exception) -> DetectorMetrics:
        """Return explicit error status for a detector infrastructure failure."""
        return DetectorMetrics(
            detector_name=detector_name,
            mode="token",
            status="error",
            error_message=str(exc),
        )

    @staticmethod
    def _parse_detectors(detectors_str: str) -> List[str]:
        """Parse the detectors argument into a list of detector keys.

        Args:
            detectors_str: 'all' or comma-separated keys: hf, presidio, heuristics.

        Returns:
            List of lowercase detector key strings.
        """
        if detectors_str.strip().lower() == "all":
            return ["hf", "presidio", "heuristics"]

        valid = {"hf", "presidio", "heuristics"}
        requested = [d.strip().lower() for d in detectors_str.split(",")]
        unknown = set(requested) - valid

        if unknown:
            logger.warning(
                "Unknown detectors ignored: %s. Valid: %s", unknown, valid
            )

        return [d for d in requested if d in valid]
