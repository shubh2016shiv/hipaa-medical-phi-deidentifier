"""
Pipeline Evaluator — Full Orchestrator PHI Detection Evaluation
================================================================

Runs the complete HIPAAPipelineOrchestrator._detect_phi_entities() method
(detection phase only — no redaction) and evaluates the merged,
overlap-resolved final entity list against ground truth.

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
    └──────────┬───────────┘
               │
    ┌──────────▼───────────┐
    │  HIPAACoverageMetric │ → LMStudioJudge (if enabled)
    └──────────────────────┘

Dependencies:
    - hipaa_deidentifier/pipeline_orchestrator.py
    - evaluation/ground_truth/annotation_schema.py
    - evaluation/metrics/span_metrics.py
    - evaluation/metrics/hipaa_coverage_metric.py

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from deepeval.test_case import LLMTestCase

from hipaa_deidentifier.models.phi_entity import PHIEntity

from ..ground_truth.annotation_schema import AnnotatedDocument
from ..metrics.hipaa_coverage_metric import HIPAACoverageMetric
from ..metrics.span_metrics import DetectorMetrics, compute_per_detector_metrics

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
        annotation_dir: Optional[str] = None,
    ) -> None:
        """Initialise the pipeline evaluator.

        Args:
            document_path: Path to the clinical note file.
            use_judge: If True, call LM Studio judge on failures.
            annotation_dir: Override directory for annotation JSON files.

        Example:
            >>> ev = PipelineEvaluator("data/.../note.txt", use_judge=False)
        """
        self.document_path = Path(document_path)
        self.use_judge = use_judge
        self.annotation_dir = annotation_dir

        self._text: str = ""
        self._annotated_doc: Optional[AnnotatedDocument] = None
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
            FileNotFoundError: If the document or annotation is not found.

        Example:
            >>> metrics = evaluator.run()
            >>> print(f"Pipeline F1: {metrics.f1:.2%}")
        """
        self._load_document_and_annotations()
        entities = self._run_full_pipeline()
        return self._score_entities(entities)

    # -----------------------------------------------------------------------
    # Document loading
    # -----------------------------------------------------------------------

    def _load_document_and_annotations(self) -> None:
        """Load document text and find the matching annotation file.

        Raises:
            FileNotFoundError: If the document or annotation is not found.
        """
        if not self.document_path.exists():
            raise FileNotFoundError(
                f"Document not found: {self.document_path}"
            )

        self._text = self.document_path.read_text(encoding="utf-8")
        logger.info("Loaded: %s (%d chars)", self.document_path.name, len(self._text))

        self._annotated_doc = AnnotatedDocument.find_annotation_for_document(
            document_path=self.document_path,
            annotation_dir=self.annotation_dir,
        )
        logger.info("Annotation: %d spans", len(self._annotated_doc.annotations))

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
            from config.config import config as global_config
            from hipaa_deidentifier.pipeline_orchestrator import HIPAAPipelineOrchestrator

            cfg = global_config.get_settings()

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
        """Score the pipeline's merged entity list against ground truth.

        Args:
            entities: Merged PHIEntity list from the full pipeline.

        Returns:
            DetectorMetrics with coverage metric and optional judge analysis.
        """
        assert self._annotated_doc is not None

        # Token-level metrics (primary)
        token_metrics = compute_per_detector_metrics(
            detector_name=_PIPELINE_LABEL,
            predicted_entities=entities,
            gold_spans=self._annotated_doc.annotations,
            text=self._text,
            mode="token",
        )

        # Span-level metrics (secondary, stored with _span suffix)
        span_metrics = compute_per_detector_metrics(
            detector_name=_PIPELINE_LABEL,
            predicted_entities=entities,
            gold_spans=self._annotated_doc.annotations,
            text=self._text,
            mode="span",
        )
        for etype, sm in span_metrics.per_type.items():
            token_metrics.per_type[f"{etype}_span"] = sm
        token_metrics.per_type["_ALL_span"] = span_metrics.overall

        # HIPAA coverage metric
        coverage_metric = HIPAACoverageMetric(threshold=0.95, judge=self._judge)
        dummy_test_case = LLMTestCase(
            input=self.document_path.name,
            actual_output=f"pipeline detected {len(entities)} entities",
        )
        coverage_metric.measure(dummy_test_case, token_metrics, self._annotated_doc)

        logger.info(
            "[%s] Recall=%.2f%% Precision=%.2f%% F1=%.2f%% | Coverage: %s",
            _PIPELINE_LABEL,
            token_metrics.recall * 100,
            token_metrics.precision * 100,
            token_metrics.f1 * 100,
            "PASS" if coverage_metric.is_successful() else "FAIL",
        )

        # Attach coverage metadata
        token_metrics.hipaa_coverage_score = coverage_metric.score          # type: ignore[attr-defined]
        token_metrics.hipaa_coverage_pass = coverage_metric.is_successful() # type: ignore[attr-defined]
        token_metrics.hipaa_coverage_reason = coverage_metric.reason        # type: ignore[attr-defined]

        return token_metrics
