"""
HIPAA Coverage Metric — DeepEval BaseMetric
============================================

A deepeval custom metric that enforces HIPAA Safe Harbor recall requirements.
Passes if recall on CRITICAL PHI categories is ≥ 95%.
On failure, invokes the LM Studio judge to explain each missed entity.

Architecture:
-------------
    hipaa_coverage_metric.py  ←  used by runners/detector_evaluator.py
          │
          ├─ span_metrics.py          (deterministic metric computation)
          └─ judges/lm_studio_judge.py (qualitative failure analysis)

Dependencies:
    - deepeval (BaseMetric, LLMTestCase)
    - span_metrics.py (DetectorMetrics)
    - judges/lm_studio_judge.py (optional, disabled in --no-judge mode)

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, List, Optional

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

if TYPE_CHECKING:
    from ..judges.lm_studio_judge import LMStudioJudge
    from .span_metrics import DetectorMetrics

logger = logging.getLogger(__name__)

# HIPAA Safe Harbor categories that are most critical for patient re-identification
_CRITICAL_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "NAME",
        "MRN",
        "DATE",
        "AGE_OVER_89",
        "LOCATION",
        "ACCOUNT_NUMBER",
        "US_SSN",
    }
)

# Recall threshold — 95% on critical identifiers (HIPAA audit standard)
_HIPAA_RECALL_THRESHOLD: float = 0.95

# Context window for judge prompts (±chars around missed entity)
_CONTEXT_WINDOW: int = 120


class HIPAACoverageMetric(BaseMetric):
    """DeepEval metric enforcing ≥95% recall on HIPAA Safe Harbor critical entities.

    This metric does NOT evaluate the quality of the generated text (it is not
    an LLM evaluation metric). It measures whether a PHI detector covers all
    critical identifiers in a clinical document.

    Passes if: recall on CRITICAL_ENTITY_TYPES >= threshold (default 0.95).
    On failure: calls LM Studio judge to explain each missed entity.

    Attributes:
        threshold: Minimum recall required to pass (default 0.95).
        judge: Optional LMStudioJudge instance. If None, judge is skipped.
        critical_types: Entity types that must meet the threshold.

    Example:
        >>> metric = HIPAACoverageMetric(threshold=0.95, judge=LMStudioJudge())
        >>> test_case = LLMTestCase(input="...", actual_output="...")
        >>> metric.measure(test_case, detector_metrics=hf_metrics, annotated_doc=doc)
        >>> print(metric.score, metric.reason)
    """

    name: str = "HIPAA Safe Harbor Coverage"

    def __init__(
        self,
        threshold: float = _HIPAA_RECALL_THRESHOLD,
        judge: Optional["LMStudioJudge"] = None,
        critical_types: frozenset[str] = _CRITICAL_ENTITY_TYPES,
    ) -> None:
        """Initialise the HIPAA coverage metric.

        Args:
            threshold: Minimum recall required on critical entities.
            judge: LMStudioJudge for qualitative failure analysis.
                   If None, missed entities are listed but not explained.
            critical_types: Set of entity types that must meet the threshold.

        Example:
            >>> metric = HIPAACoverageMetric(threshold=0.95, judge=LMStudioJudge())
        """
        self.threshold = threshold
        self.judge = judge
        self.critical_types = critical_types
        # deepeval requires these attributes
        self.score: float | None = 0.0
        self.reason: str | None = ""
        self.success: bool | None = False

    def measure(
        self,
        test_case: LLMTestCase,
        detector_metrics: "DetectorMetrics",
        annotated_doc: Any,
    ) -> float:
        """Compute the HIPAA coverage score and optionally invoke the judge.

        This overrides deepeval's BaseMetric.measure signature with extra
        domain-specific args. The score is the recall on critical entity types.

        Args:
            test_case: deepeval LLMTestCase (used for framework compatibility).
            detector_metrics: DetectorMetrics from span_metrics.py.
            annotated_doc: The AnnotatedDocument with ground truth spans.

        Returns:
            Float recall score on critical entity types (0.0–1.0).

        Example:
            >>> score = metric.measure(test_case, hf_metrics, annotated_doc)
        """
        # Compute recall on critical entity types only
        critical_recall = self._compute_critical_recall(detector_metrics)
        self.score = round(critical_recall, 4)

        # Identify missed critical entities
        missed_critical_spans = self._find_missed_critical_spans(
            detector_metrics, annotated_doc
        )

        # Determine pass/fail
        self.success = self.score >= self.threshold

        # Build reason
        if self.success:
            self.reason = (
                f"PASS — Critical entity recall: {self.score:.1%} "
                f"(threshold: {self.threshold:.0%}). "
                f"Missed: {len(missed_critical_spans)} critical PHI entities."
            )
        else:
            self.reason = (
                f"FAIL — Critical entity recall: {self.score:.1%} "
                f"(threshold: {self.threshold:.0%}). "
                f"Missed: {len(missed_critical_spans)} critical PHI entities "
                f"({', '.join(s.entity_type for s in missed_critical_spans[:5])}"
                f"{'...' if len(missed_critical_spans) > 5 else ''})."
            )

        # Invoke judge for missed entities (if available)
        if missed_critical_spans and self.judge is not None:
            judge_analysis = self._run_judge_on_missed_entities(
                missed_critical_spans, annotated_doc, detector_metrics.detector_name
            )
            self.reason += f"\n\nLM Studio Judge Analysis:\n{judge_analysis}"

        logger.info(
            "HIPAACoverageMetric [%s]: score=%.3f success=%s missed=%d",
            detector_metrics.detector_name,
            self.score,
            self.success,
            len(missed_critical_spans),
        )

        return self.score

    async def a_measure(
        self,
        test_case: LLMTestCase,
        detector_metrics: "DetectorMetrics",
        annotated_doc: Any,
    ) -> float:
        """Async version of measure — delegates to synchronous implementation.

        Args:
            test_case: deepeval LLMTestCase.
            detector_metrics: DetectorMetrics from span_metrics.py.
            annotated_doc: The AnnotatedDocument with ground truth spans.

        Returns:
            Float recall score on critical entity types.
        """
        # WHY: judge calls are synchronous via httpx; we wrap here for compatibility
        return self.measure(test_case, detector_metrics, annotated_doc)

    def is_successful(self) -> bool:
        """Return True if the last measure() call passed the threshold.

        Returns:
            Boolean pass/fail from most recent evaluation.
        """
        return bool(self.success)

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _compute_critical_recall(self, metrics: "DetectorMetrics") -> float:
        """Compute recall over CRITICAL entity types only.

        Args:
            metrics: DetectorMetrics with per_type breakdown.

        Returns:
            Weighted recall across critical entity types (by gold span count).
        """
        total_tp = 0.0
        total_fn = 0.0

        for entity_type in self.critical_types:
            type_m = metrics.per_type.get(entity_type)
            if type_m is None:
                continue
            total_tp += type_m.true_positives
            total_fn += type_m.false_negatives

        denom = total_tp + total_fn
        return total_tp / denom if denom > 0 else 1.0

    def _find_missed_critical_spans(
        self,
        metrics: "DetectorMetrics",
        annotated_doc: Any,
    ) -> List[Any]:
        """Return gold spans that were missed and are of a critical type.

        Args:
            metrics: DetectorMetrics with missed_gold_indices.
            annotated_doc: AnnotatedDocument with full annotations list.

        Returns:
            List of AnnotatedSpan objects that were missed.
        """
        missed = []
        for idx in metrics.missed_gold_indices:
            if idx < len(annotated_doc.annotations):
                span = annotated_doc.annotations[idx]
                if span.entity_type in self.critical_types:
                    missed.append(span)
        return missed

    def _run_judge_on_missed_entities(
        self,
        missed_spans: List[Any],
        annotated_doc: Any,
        detector_name: str,
    ) -> str:
        """Call the LM Studio judge for each missed critical entity.

        Args:
            missed_spans: List of missed AnnotatedSpan objects.
            annotated_doc: The full annotated document (for context extraction).
            detector_name: Name of the failing detector.

        Returns:
            Multi-entity judge analysis as a formatted string.
        """
        from ..judges.lm_studio_judge import LMStudioJudge

        analyses: List[str] = []
        for span in missed_spans[:5]:  # Limit to 5 to avoid long runtimes
            context = self._extract_context(annotated_doc.text, span.start, span.end)
            prompt = LMStudioJudge.build_missed_entity_prompt(
                entity_value=span.value,
                entity_type=span.entity_type,
                detector_name=detector_name,
                context_snippet=context,
                hipaa_rule=span.hipaa_rule,
            )

            logger.debug(
                "Calling judge for missed: %r (%s)", span.value, span.entity_type
            )
            assert self.judge is not None
            verdict = self.judge.generate(prompt)

            analyses.append(
                f"❌ MISSED [{span.entity_type}] {span.value!r} "
                f"(rule: {span.hipaa_rule}, risk: {span.severity.upper()})\n"
                f"{verdict}"
            )

        return "\n\n".join(analyses)

    @staticmethod
    def _extract_context(text: str, start: int, end: int) -> str:
        """Extract ±_CONTEXT_WINDOW characters around a span.

        Args:
            text: Full document text.
            start: Span start offset.
            end: Span end offset.

        Returns:
            Context string with the span highlighted by >>> <<<.
        """
        ctx_start = max(0, start - _CONTEXT_WINDOW)
        ctx_end = min(len(text), end + _CONTEXT_WINDOW)

        before = text[ctx_start:start]
        span_text = text[start:end]
        after = text[end:ctx_end]

        return f"{before}>>>{span_text}<<<{after}"
