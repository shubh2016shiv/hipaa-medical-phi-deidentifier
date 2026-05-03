"""
HF Confidence Filter — Drops HF-sourced entities below a confidence threshold.

Architecture:
-------------
    ┌─────────────────────────┐     ┌──────────────────────────┐
    │  FalsePositiveGuardrail │────▶│  HFConfidenceFilter      │
    │  (fp_guardrail.py)      │     │  (hf_confidence_filter)  │
    └─────────────────────────┘     └──────────────────────────┘

    The HF model (obi/deid_bert_i2b2) produces real calibrated probabilities.
    Entities below the threshold are discarded before reaching the redactor.
    All non-HF entities are passed through unchanged.

Dependencies:
    - models/phi_entity.py  — PHIEntity dataclass
    - utils/logger.py       — Structured logging

Author: HIPAA De-identification System
Last Updated: 2026-05-03
"""

from __future__ import annotations

import logging
from typing import List, Sequence

from ...models.phi_entity import PHIEntity

logger = logging.getLogger(__name__)

_HF_SOURCE = "hf"


class HFConfidenceFilter:
    """Filters HF-sourced PHI entities by confidence threshold.

    Entities with source == "hf" and confidence below the threshold are
    dropped. All other entities are passed through without modification.

    Example:
        >>> f = HFConfidenceFilter(threshold=0.9)
        >>> kept = f.filter([entity_at_0_95, entity_at_0_80])
        >>> assert len(kept) == 1
    """

    def __init__(self, threshold: float = 0.9) -> None:
        """Initialize with the minimum acceptable HF confidence score.

        Args:
            threshold: Entities from the HF model with confidence strictly
                below this value are discarded. Must be in [0.0, 1.0].

        Raises:
            ValueError: If threshold is outside [0.0, 1.0].
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be in [0.0, 1.0], got {threshold!r}")
        self._threshold = threshold
        logger.info("HFConfidenceFilter initialised with threshold=%.2f", threshold)

    def filter(self, entities: Sequence[PHIEntity]) -> List[PHIEntity]:
        """Drop HF entities below the confidence threshold.

        Args:
            entities: Detected PHI entities from all detectors.

        Returns:
            Entities with low-confidence HF detections removed.
        """
        validated: List[PHIEntity] = []
        for entity in entities:
            if self._should_drop(entity):
                logger.debug(
                    "HF drop: %s confidence=%.3f < %.2f",
                    entity.category,
                    entity.confidence,
                    self._threshold,
                )
            else:
                validated.append(entity)
        return validated

    def _should_drop(self, entity: PHIEntity) -> bool:
        """Return True if this entity should be discarded.

        Args:
            entity: The entity to evaluate.

        Returns:
            True when the entity is HF-sourced and below threshold.
        """
        source = getattr(entity, "source", "unknown")
        return source == _HF_SOURCE and entity.confidence < self._threshold
