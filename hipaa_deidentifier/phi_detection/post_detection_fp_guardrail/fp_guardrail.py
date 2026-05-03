"""
False Positive Guardrail — Orchestrates all post-detection entity filters.

Architecture:
-------------
    ┌─────────────────────────────┐     ┌──────────────────────────┐
    │  HIPAAPipelineOrchestrator  │────▶│  FalsePositiveGuardrail  │
    │  (pipeline_orchestrator.py) │     │  (fp_guardrail.py)       │
    └─────────────────────────────┘     └────────────┬─────────────┘
                                                     │
                          ┌──────────────────────────┼───────────────────────┐
                          ▼                          ▼                       ▼
               ┌──────────────────┐   ┌─────────────────────────┐  ┌───────────────────────┐
               │HFConfidenceFilter│   │PresidioStructuralValidator│  │NameOrganization       │
               │                  │   │                         │  │ContextFilter          │
               │ Drops HF entities│   │ Drops spaCy-flat-0.85   │  │ Drops clinical-phrase │
               │ below threshold  │   │ that fail category regex │  │ NAME/ORG detections   │
               └──────────────────┘   └─────────────────────────┘  └───────────────────────┘
                          │                          │                       │
                          └──────────────────────────┴───────────────────────┘
                                                     │
                                                     ▼
                                            PHIRedactor.redact_text()

Filter execution order:
    1. HFConfidenceFilter       — confidence gate on real model probabilities
    2. PresidioStructuralValidator — category-regex gate on flat-0.85 entities
    3. NameOrganizationContextFilter — deny-list gate on NAME/ORG entities

Dependencies:
    - hf_confidence_filter.py   — HFConfidenceFilter
    - structural_validator.py   — PresidioStructuralValidator
    - name_context_filter.py    — NameOrganizationContextFilter
    - models/phi_entity.py      — PHIEntity dataclass
    - utils/logger.py           — Structured logging

Author: HIPAA De-identification System
Last Updated: 2026-05-03
"""

from __future__ import annotations

import logging
from typing import List, Sequence

from ...models.phi_entity import PHIEntity
from .hf_confidence_filter import HFConfidenceFilter
from .name_context_filter import NameOrganizationContextFilter
from .structural_validator import PresidioStructuralValidator

logger = logging.getLogger(__name__)


class FalsePositiveGuardrail:
    """Orchestrates post-detection false positive filtering before redaction.

    Applies three independent, ordered filter passes to the raw entity list
    produced by the detection pipeline.  Each filter has a single concern;
    none modifies the redactor or the detection pipeline.

    Example:
        >>> guardrail = FalsePositiveGuardrail(hf_threshold=0.9)
        >>> clean_entities = guardrail.filter(raw_entities, original_text)
    """

    def __init__(self, hf_threshold: float = 0.9) -> None:
        """Construct the guardrail with injected sub-filters.

        Args:
            hf_threshold: Minimum confidence for HF model detections to be
                kept.  Values in [0.0, 1.0].  Default 0.9 is calibrated from
                evaluation results where all confirmed true-positive HF
                detections scored >= 0.92.

        Raises:
            ValueError: Propagated from HFConfidenceFilter if threshold is
                outside [0.0, 1.0].
        """
        self._hf_filter = HFConfidenceFilter(threshold=hf_threshold)
        self._structural_validator = PresidioStructuralValidator()
        self._name_context_filter = NameOrganizationContextFilter()
        logger.info(
            "FalsePositiveGuardrail initialised (hf_threshold=%.2f)", hf_threshold
        )

    def filter(self, entities: Sequence[PHIEntity], text: str) -> List[PHIEntity]:
        """Run all filter passes and return validated entities.

        Passes are applied in order: HF confidence → structural → context.
        Each pass only discards; it never reorders or modifies entities.

        Args:
            entities: Raw PHI entities from the detection pipeline.
            text: Original document text passed to structural validators
                that may need surrounding context in future extensions.

        Returns:
            Subset of entities that passed all three filter passes.
        """
        initial_count = len(entities)

        after_hf = self._hf_filter.filter(entities)
        after_structural = self._structural_validator.filter(after_hf, text)
        after_context = self._name_context_filter.filter(after_structural)

        dropped = initial_count - len(after_context)
        if dropped > 0:
            logger.info(
                "Guardrail dropped %d of %d entities (kept %d)",
                dropped,
                initial_count,
                len(after_context),
            )
        return after_context
