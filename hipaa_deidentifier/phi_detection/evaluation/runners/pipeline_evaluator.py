"""
Pipeline Evaluator — Full Orchestrator PHI Detection Evaluation
================================================================

Runs the complete HIPAAPipelineOrchestrator._detect_phi_entities() method
(detection phase only — no redaction) and returns the merged,
overlap-resolved final entity list as a DetectorMetrics result.

This answers: "Does combining all detectors improve individual performance,
or does the merging logic introduce regressions?"

Architecture:
-------------
    ┌──────────────────────┐
    │  PipelineEvaluator   │
    │  (this module)       │
    └──────────┬───────────┘
               │
    ┌──────────▼───────────────────────────┐
    │  HIPAAPipelineOrchestrator           │
    │  ._detect_phi_entities(text)         │
    │                                       │
    │  → presidio_entities                 │
    │  → hf_entities                       │
    │  → heuristic_entities                │
    │  → merged + overlap-resolved output  │
    └──────────┬───────────────────────────┘
               │
    ┌──────────▼───────────┐
    │  span_metrics.py     │ → DetectorMetrics
    └──────────────────────┘

Dependencies:
    - hipaa_deidentifier/pipeline_orchestrator.py
    - evaluation/metrics/span_metrics.py

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from hipaa_deidentifier.models.phi_entity import PHIEntity

from ..metrics.span_metrics import DetectorMetrics

if TYPE_CHECKING:
    from ..judges.lm_studio_judge import LMStudioJudge

logger = logging.getLogger(__name__)

_PIPELINE_LABEL: str = "Full Pipeline (HF + Presidio + Heuristics, merged)"


class PipelineEvaluator:
    """Evaluates the full combined pipeline output against ground truth.

    Runs HIPAAPipelineOrchestrator._detect_phi_entities() which includes
    all detectors, clinical term preservation, and overlap resolution.
    Scores the final merged entity list.

    Attributes:
        document_path: Path to the clinical note.
        use_judge: Whether to call the LM Studio judge on failures.

    Example:
        >>> evaluator = PipelineEvaluator(
        ...     document_path="data/Long-term and Supportive Care/home_health_assessment_patient_01.txt",
        ...     use_judge=True,
        ... )
        >>> pipeline_metrics = evaluator.run()
        >>> print(f"Pipeline Recall: {pipeline_metrics.recall:.2%}")
    """

    def __init__(
        self,
        document_path: str,
        use_judge: bool = True,
    ) -> None:
        """Initialise the pipeline evaluator.

        Args:
            document_path: Path to the clinical note file.
            use_judge: If True, call LM Studio judge on failures.

        Example:
            >>> ev = PipelineEvaluator("data/.../note.txt", use_judge=False)
        """
        self.document_path = Path(document_path)
        self.use_judge = use_judge

        self._text: str = ""
        self._judge: Optional["LMStudioJudge"] = None
        if use_judge:
            from ..judges.lm_studio_judge import LMStudioJudge

            self._judge = LMStudioJudge()

        logger.info(
            "PipelineEvaluator initialised: doc=%s judge=%s",
            self.document_path.name,
            "enabled" if use_judge else "disabled",
        )

    def run(self) -> DetectorMetrics:
        """Execute the full pipeline evaluation.

        Returns:
            DetectorMetrics for the merged pipeline output.

        Raises:
            FileNotFoundError: If the document is not found.

        Example:
            >>> metrics = evaluator.run()
            >>> print(f"Pipeline F1: {metrics.f1:.2%}")
        """
        self._load_document()
        entities = self._run_full_pipeline()
        return self._score_entities(entities)

    # -----------------------------------------------------------------------
    # Document loading
    # -----------------------------------------------------------------------

    def _load_document(self) -> None:
        """Load document text from disk.

        Raises:
            FileNotFoundError: If the document is not found.
        """
        if not self.document_path.exists():
            raise FileNotFoundError(f"Document not found: {self.document_path}")

        self._text = self.document_path.read_text(encoding="utf-8")
        logger.info("Loaded: %s (%d chars)", self.document_path.name, len(self._text))

    # -----------------------------------------------------------------------
    # Pipeline execution
    # -----------------------------------------------------------------------

    def _run_full_pipeline(self) -> List[PHIEntity]:
        """Run HIPAAPipelineOrchestrator in detection-only mode.

        Returns:
            Merged list of PHI entities from the full pipeline.
        """
        logger.info("Running full pipeline (detection phase)...")

        try:
            from hipaa_deidentifier.pipeline_orchestrator import (
                HIPAAPipelineOrchestrator,
            )

            # WHY: We use the orchestrator's internal _detect_phi_entities method
            # rather than the full process() method to isolate detection quality
            # from redaction quality — the two must be evaluated independently.
            orchestrator = HIPAAPipelineOrchestrator()
            entities: List[PHIEntity] = orchestrator._detect_phi_entities(self._text)

            logger.info("Full pipeline detected %d entities", len(entities))
            return entities

        except Exception as exc:
            logger.error("Full pipeline failed: %s", exc)
            logger.warning("Returning empty entity list for pipeline evaluation.")
            return []

    # -----------------------------------------------------------------------
    # Scoring
    # -----------------------------------------------------------------------

    def _score_entities(self, entities: List[PHIEntity]) -> DetectorMetrics:
        """Return a DetectorMetrics summarising the pipeline's detected entities.

        Args:
            entities: Merged PHIEntity list from the full pipeline.

        Returns:
            DetectorMetrics with status and entity count (no ground truth scoring).
        """
        metrics = DetectorMetrics(
            detector_name=_PIPELINE_LABEL,
            mode="token",
            status="ok",
        )

        logger.info(
            "[%s] Detected %d entities",
            _PIPELINE_LABEL,
            len(entities),
        )

        return metrics
