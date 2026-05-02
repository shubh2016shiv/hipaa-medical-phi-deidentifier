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
    │  detect_section_headers()  \\                   │
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

from hipaa_deidentifier.models.phi_entity import PHIEntity
from hipaa_deidentifier.phi_detection.clinical_patterns import (
    detect_clinical_phi,
)

from ..metrics.span_metrics import DetectorMetrics

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
    ) -> None:
        """Initialise the detector evaluator.

        Args:
            document_path: Path to the clinical note file.
            detectors: Comma-separated detector names or 'all'.
            use_judge: If True, call LM Studio judge on failures.

        Example:
            >>> ev = DetectorEvaluator("data/.../note.txt", detectors="hf,presidio")
        """
        self.document_path = Path(document_path)
        self.use_judge = use_judge

        self._requested_detectors = self._parse_detectors(detectors)
        self._text: str = ""
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
        self._load_document()
        results: Dict[str, DetectorMetrics] = {}

        if "hf" in self._requested_detectors:
            results[_DETECTOR_LABELS["hf"]] = self._run_hf_detector()

        if "presidio" in self._requested_detectors:
            results[_DETECTOR_LABELS["presidio"]] = self._run_presidio_detector()

        if "heuristics" in self._requested_detectors:
            results[_DETECTOR_LABELS["heuristics"]] = self._run_heuristics_detector()

        logger.info("DetectorEvaluator complete: %d detectors evaluated", len(results))
        return results

    # -----------------------------------------------------------------------
    # Document loading
    # -----------------------------------------------------------------------

    def _load_document(self) -> None:
        """Load the document text from disk.

        Raises:
            FileNotFoundError: If the document is not found.
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
            from hipaa_deidentifier.phi_detection.identifier.huggingface_model_identifier import (
                HFIdentifier,
            )

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
            from hipaa_deidentifier.phi_detection.identifier.presidio_identifier import (
                PresidioIdentifier,
            )

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
        """Return a DetectorMetrics summarising the detector's detected entities.

        Args:
            detector_name: Human-readable detector label.
            entities: Predicted PHIEntity list from the detector.

        Returns:
            DetectorMetrics with status and entity count (no ground truth scoring).
        """
        metrics = DetectorMetrics(
            detector_name=detector_name,
            mode="token",
            status="ok",
        )
        logger.info("[%s] Detected %d entities", detector_name, len(entities))
        return metrics

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
            logger.warning("Unknown detectors ignored: %s. Valid: %s", unknown, valid)

        return [d for d in requested if d in valid]
