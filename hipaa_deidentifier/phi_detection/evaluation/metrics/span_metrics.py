"""
Span-Level PHI Detection Metrics
==================================

Pure Python, deterministic computation of Precision, Recall, F1, FNR and FPR
for PHI detection evaluation. No LLM or external dependencies.

Two evaluation modes:
  - token_level: Every character position is either covered or not.
    Partial span detection (e.g. catching "Margaret Rose" but missing "Sullivan")
    scores proportionally better than a complete miss. Primary metric.
  - span_level: An entity must overlap ≥50% of the gold span to count as a hit.
    Strict, binary. Secondary metric for HIPAA audit reporting.

Architecture:
-------------
    span_metrics.py  ←  used by:
      ├─ runners/detector_evaluator.py
      ├─ runners/pipeline_evaluator.py
      └─ metrics/hipaa_coverage_metric.py

Dependencies: None (stdlib only).

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Sequence

logger = logging.getLogger(__name__)

EvaluationMode = Literal["token", "span"]

# Overlap threshold for span-level matching (50% of gold span must be covered)
_SPAN_OVERLAP_THRESHOLD: float = 0.50


@dataclass
class TypeMetrics:
    """Metrics for a single PHI entity type.

    Attributes:
        entity_type: HIPAA category (e.g. NAME, MRN).
        true_positives: Correctly detected entity tokens / spans.
        false_positives: Over-detected (non-PHI labelled as PHI).
        false_negatives: Missed entity tokens / spans.
        precision: TP / (TP + FP). How clean the predictions are.
        recall: TP / (TP + FN). How complete the detection is (primary).
        f1: Harmonic mean of precision and recall.
        false_negative_rate: FN / (TP + FN). Proportion of PHI missed.
        false_positive_rate: FP / (FP + TN). Over-detection rate.
    """

    entity_type: str
    true_positives: float = 0.0
    false_positives: float = 0.0
    false_negatives: float = 0.0
    true_negatives: float = 0.0

    @property
    def precision(self) -> float:
        """TP / (TP + FP). Returns 1.0 if no predictions were made."""
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom > 0 else 1.0

    @property
    def recall(self) -> float:
        """TP / (TP + FN). Returns 1.0 if no gold entities exist."""
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom > 0 else 1.0

    @property
    def f1(self) -> float:
        """Harmonic mean of precision and recall."""
        p, r = self.precision, self.recall
        denom = p + r
        return 2 * p * r / denom if denom > 0 else 0.0

    @property
    def false_negative_rate(self) -> float:
        """FN / (TP + FN). Proportion of PHI missed (compliance risk)."""
        denom = self.true_positives + self.false_negatives
        return self.false_negatives / denom if denom > 0 else 0.0

    @property
    def false_positive_rate(self) -> float:
        """FP / (FP + TN). Over-detection / over-redaction rate."""
        denom = self.false_positives + self.true_negatives
        return self.false_positives / denom if denom > 0 else 0.0


@dataclass
class DetectorMetrics:
    """Full metrics for a single detector run against one document.

    Attributes:
        detector_name: Human-readable detector identifier.
        mode: Evaluation mode used ('token' or 'span').
        overall: Aggregate TypeMetrics across all entity types.
        per_type: Per-entity-type breakdown.
        missed_gold_indices: Indices into gold spans that were not detected.
        fp_predicted_indices: Indices into predictions that are false positives.
        status: Evaluation status ('ok' or 'error').
        error_message: Detector/runtime error message for failed evaluations.
    """

    detector_name: str
    mode: EvaluationMode
    overall: TypeMetrics = field(default_factory=lambda: TypeMetrics("ALL"))
    per_type: Dict[str, TypeMetrics] = field(default_factory=dict)
    missed_gold_indices: List[int] = field(default_factory=list)
    fp_predicted_indices: List[int] = field(default_factory=list)
    status: str = "ok"
    error_message: str | None = None

    @property
    def recall(self) -> float:
        """Convenience accessor for overall recall."""
        return self.overall.recall

    @property
    def precision(self) -> float:
        """Convenience accessor for overall precision."""
        return self.overall.precision

    @property
    def f1(self) -> float:
        """Convenience accessor for overall F1."""
        return self.overall.f1

    @property
    def false_negative_rate(self) -> float:
        """Convenience accessor for overall FNR."""
        return self.overall.false_negative_rate


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _gold_to_token_set(gold_spans: Sequence) -> set[int]:
    """Convert a list of AnnotatedSpan objects into a set of character positions.

    Args:
        gold_spans: Sequence of AnnotatedSpan objects (must have .start, .end).

    Returns:
        Set of integer character positions covered by any gold span.
    """
    positions: set[int] = set()
    for span in gold_spans:
        positions.update(range(span.start, span.end))
    return positions


def _pred_to_token_set(pred_entities: Sequence) -> set[int]:
    """Convert a list of PHIEntity objects into a set of character positions.

    Args:
        pred_entities: Sequence of PHIEntity objects (must have .start, .end).

    Returns:
        Set of integer character positions covered by any predicted entity.
    """
    positions: set[int] = set()
    for entity in pred_entities:
        positions.update(range(entity.start, entity.end))
    return positions


def _gold_to_token_set_by_type(gold_spans: Sequence, entity_type: str) -> set[int]:
    """Character positions covered by gold spans of a specific entity type."""
    return _gold_to_token_set(s for s in gold_spans if s.entity_type == entity_type)


def _pred_to_token_set_by_type(pred_entities: Sequence, entity_type: str) -> set[int]:
    """Character positions covered by predictions of a specific entity type."""
    return _pred_to_token_set(e for e in pred_entities if e.category == entity_type)


def _count_true_negatives(
    text: str,
    gold_positions: set[int],
    pred_positions: set[int],
) -> float:
    """Estimate true-negative token count.

    True negatives are positions in the document that are NOT PHI and
    were NOT predicted as PHI. Used for FPR computation.

    Args:
        text: Full document text.
        gold_positions: Set of positions that ARE PHI (from ground truth).
        pred_positions: Set of positions predicted as PHI.

    Returns:
        Count of character positions that are neither gold nor predicted PHI.
    """
    document_positions = set(range(len(text)))
    return float(len(document_positions - gold_positions - pred_positions))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_token_level_metrics(
    predicted_entities: Sequence,
    gold_spans: Sequence,
    text: str,
    entity_types: Sequence[str] | None = None,
) -> DetectorMetrics:
    """Compute token-level Precision, Recall, F1, FNR, FPR.

    Every character position is either covered (TP/FP) or missed (FN/TN).
    Partial span detection scores proportionally — better than a complete miss.

    Args:
        predicted_entities: List of PHIEntity objects from a detector.
        gold_spans: List of AnnotatedSpan objects from ground truth.
        text: Full document text (used for TN estimation).
        entity_types: If provided, only evaluate these entity types.
                      If None, evaluates all types present in gold + predicted.

    Returns:
        DetectorMetrics with overall and per-type breakdowns.

    Example:
        >>> metrics = compute_token_level_metrics(
        ...     predicted_entities=hf_entities,
        ...     gold_spans=doc.annotations,
        ...     text=document_text,
        ... )
        >>> print(f"Recall: {metrics.recall:.2%}")
    """
    # Determine which entity types to evaluate
    if entity_types is None:
        gold_types = {s.entity_type for s in gold_spans}
        pred_types = {e.category for e in predicted_entities}
        all_types = gold_types | pred_types
    else:
        all_types = set(entity_types)

    per_type: Dict[str, TypeMetrics] = {}

    # Overall token-level counters
    all_gold_positions = _gold_to_token_set(gold_spans)
    all_pred_positions = _pred_to_token_set(predicted_entities)
    tn_count = _count_true_negatives(text, all_gold_positions, all_pred_positions)

    overall_tp = float(len(all_gold_positions & all_pred_positions))
    overall_fp = float(len(all_pred_positions - all_gold_positions))
    overall_fn = float(len(all_gold_positions - all_pred_positions))

    overall = TypeMetrics(
        entity_type="ALL",
        true_positives=overall_tp,
        false_positives=overall_fp,
        false_negatives=overall_fn,
        true_negatives=tn_count,
    )

    # Per-type breakdown
    for entity_type in all_types:
        gold_pos = _gold_to_token_set_by_type(gold_spans, entity_type)
        pred_pos = _pred_to_token_set_by_type(predicted_entities, entity_type)

        type_tn = _count_true_negatives(text, gold_pos, pred_pos)
        per_type[entity_type] = TypeMetrics(
            entity_type=entity_type,
            true_positives=float(len(gold_pos & pred_pos)),
            false_positives=float(len(pred_pos - gold_pos)),
            false_negatives=float(len(gold_pos - pred_pos)),
            true_negatives=type_tn,
        )

    # Track which gold spans were entirely missed (for LLM judge)
    missed_gold_indices = [
        idx for idx, span in enumerate(gold_spans)
        if not any(
            pos in all_pred_positions
            for pos in range(span.start, span.end)
        )
    ]

    # Track false positive predicted entities (entirely outside gold)
    fp_predicted_indices = [
        idx for idx, entity in enumerate(predicted_entities)
        if not any(
            pos in all_gold_positions
            for pos in range(entity.start, entity.end)
        )
    ]

    logger.debug(
        "Token-level metrics: TP=%.0f FP=%.0f FN=%.0f | "
        "missed=%d FP_entities=%d",
        overall_tp, overall_fp, overall_fn,
        len(missed_gold_indices), len(fp_predicted_indices),
    )

    return DetectorMetrics(
        detector_name="",  # caller sets this
        mode="token",
        overall=overall,
        per_type=per_type,
        missed_gold_indices=missed_gold_indices,
        fp_predicted_indices=fp_predicted_indices,
    )


def compute_span_level_metrics(
    predicted_entities: Sequence,
    gold_spans: Sequence,
    text: str,
    overlap_threshold: float = _SPAN_OVERLAP_THRESHOLD,
    entity_types: Sequence[str] | None = None,
) -> DetectorMetrics:
    """Compute span-level Precision, Recall, F1, FNR, FPR.

    A predicted entity is a TP if it overlaps ≥50% of any gold span
    of the same entity type. Strict binary matching per span.

    Args:
        predicted_entities: List of PHIEntity objects from a detector.
        gold_spans: List of AnnotatedSpan objects from ground truth.
        text: Full document text (used for TN estimation).
        overlap_threshold: Minimum fractional overlap to count as a hit.
        entity_types: If provided, only evaluate these entity types.

    Returns:
        DetectorMetrics with overall and per-type breakdowns.

    Example:
        >>> metrics = compute_span_level_metrics(
        ...     predicted_entities=presidio_entities,
        ...     gold_spans=doc.annotations,
        ...     text=document_text,
        ... )
        >>> print(f"Span-level F1: {metrics.f1:.2%}")
    """
    if entity_types is None:
        gold_types = {s.entity_type for s in gold_spans}
        pred_types = {e.category for e in predicted_entities}
        all_types = gold_types | pred_types
    else:
        all_types = set(entity_types)

    per_type: Dict[str, TypeMetrics] = {}

    overall_tp = 0.0
    overall_fp = 0.0
    overall_fn = 0.0

    all_gold_positions = _gold_to_token_set(gold_spans)
    all_pred_positions = _pred_to_token_set(predicted_entities)
    tn_count = _count_true_negatives(text, all_gold_positions, all_pred_positions)

    missed_gold_indices: List[int] = []
    fp_predicted_indices: List[int] = []

    for entity_type in all_types:
        type_gold = [s for s in gold_spans if s.entity_type == entity_type]
        type_pred = [e for e in predicted_entities if e.category == entity_type]

        matched_gold: set[int] = set()
        matched_pred: set[int] = set()

        for p_idx, pred in enumerate(type_pred):
            pred_positions = set(range(pred.start, pred.end))
            hit = False
            for g_idx, gold in enumerate(type_gold):
                if g_idx in matched_gold:
                    continue
                gold_positions = set(range(gold.start, gold.end))
                if not gold_positions:
                    continue
                overlap = len(pred_positions & gold_positions) / len(gold_positions)
                if overlap >= overlap_threshold:
                    matched_gold.add(g_idx)
                    matched_pred.add(p_idx)
                    hit = True
                    break
            if not hit:
                fp_predicted_indices.append(
                    next(
                        (i for i, e in enumerate(predicted_entities) if e is pred),
                        -1,
                    )
                )

        tp = float(len(matched_gold))
        fp = float(len(type_pred) - len(matched_pred))
        fn = float(len(type_gold) - len(matched_gold))

        # Track missed gold indices for this type
        for g_idx, gold in enumerate(type_gold):
            if g_idx not in matched_gold:
                gold_global_idx = next(
                    (i for i, s in enumerate(gold_spans) if s is gold), -1
                )
                if gold_global_idx >= 0:
                    missed_gold_indices.append(gold_global_idx)

        type_tn = _count_true_negatives(
            text,
            _gold_to_token_set_by_type(gold_spans, entity_type),
            _pred_to_token_set_by_type(predicted_entities, entity_type),
        )
        per_type[entity_type] = TypeMetrics(
            entity_type=entity_type,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            true_negatives=type_tn,
        )

        overall_tp += tp
        overall_fp += fp
        overall_fn += fn

    overall = TypeMetrics(
        entity_type="ALL",
        true_positives=overall_tp,
        false_positives=overall_fp,
        false_negatives=overall_fn,
        true_negatives=tn_count,
    )

    logger.debug(
        "Span-level metrics: TP=%.0f FP=%.0f FN=%.0f | missed=%d FP=%d",
        overall_tp, overall_fp, overall_fn,
        len(missed_gold_indices), len(fp_predicted_indices),
    )

    return DetectorMetrics(
        detector_name="",
        mode="span",
        overall=overall,
        per_type=per_type,
        missed_gold_indices=missed_gold_indices,
        fp_predicted_indices=fp_predicted_indices,
    )


def compute_per_detector_metrics(
    detector_name: str,
    predicted_entities: Sequence,
    gold_spans: Sequence,
    text: str,
    mode: EvaluationMode = "token",
) -> DetectorMetrics:
    """Unified entry point: compute metrics for one detector run.

    Args:
        detector_name: Label for the detector (e.g. 'HFIdentifier').
        predicted_entities: List of PHIEntity objects.
        gold_spans: List of AnnotatedSpan objects.
        text: Full document text.
        mode: 'token' (primary) or 'span' (secondary).

    Returns:
        DetectorMetrics with detector_name populated.

    Example:
        >>> metrics = compute_per_detector_metrics(
        ...     detector_name="HFIdentifier",
        ...     predicted_entities=hf_entities,
        ...     gold_spans=doc.annotations,
        ...     text=document_text,
        ... )
        >>> print(f"HF Recall: {metrics.recall:.2%}")
    """
    if mode == "token":
        result = compute_token_level_metrics(predicted_entities, gold_spans, text)
    else:
        result = compute_span_level_metrics(predicted_entities, gold_spans, text)

    result.detector_name = detector_name
    return result
