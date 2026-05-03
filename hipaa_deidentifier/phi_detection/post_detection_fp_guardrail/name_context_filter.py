"""
Name / Organisation Context Filter — Deny-list validation for NAME and ORGANIZATION.

Architecture:
-------------
    ┌─────────────────────────┐     ┌──────────────────────────────┐
    │  FalsePositiveGuardrail │────▶│  NameOrganizationContextFilter│
    │  (fp_guardrail.py)      │     │  (name_context_filter.py)    │
    └─────────────────────────┘     └──────────────────────────────┘

    NAME and ORGANIZATION entities have no structural fingerprint — any
    sequence of proper nouns can match.  spaCy's NER routinely produces
    false positives for clinical phrases ("verbalized understanding"),
    section headers ("Falls\nGoal"), and relational terms ("Daughter").

    This filter discards those detections using deny-lists from
    RedactionConfig that are already maintained for the redaction layer.
    Only Presidio-sourced NAME/ORG entities are evaluated; HF-sourced
    entities are handled by HFConfidenceFilter upstream.

Dependencies:
    - models/phi_entity.py               — PHIEntity dataclass
    - phi_redaction/redaction_config.py  — CLINICAL_TERMS, COMMON_HEADERS,
                                           HEADER_PHRASES, CLINICAL_PHRASES
    - utils/logger.py                    — Structured logging

Author: HIPAA De-identification System
Last Updated: 2026-05-03
"""

from __future__ import annotations

import logging
from typing import FrozenSet, List, Sequence

from ...models.phi_entity import PHIEntity
from ...phi_redaction.redaction_config import RedactionConfig

logger = logging.getLogger(__name__)

_FILTERED_CATEGORIES: FrozenSet[str] = frozenset({"NAME", "ORGANIZATION"})
_PRESIDIO_SOURCES: FrozenSet[str] = frozenset({"presidio", "presidio_clinical"})
_MIN_NAME_LENGTH = 2


class NameOrganizationContextFilter:
    """Removes Presidio NAME/ORGANIZATION false positives using deny-lists.

    Applies only to entities where source is 'presidio' or
    'presidio_clinical' and category is NAME or ORGANIZATION.
    All other entities pass through unchanged.

    Example:
        >>> f = NameOrganizationContextFilter()
        >>> kept = f.filter([clinical_phrase_entity, real_name_entity])
        >>> assert len(kept) == 1
    """

    def filter(self, entities: Sequence[PHIEntity]) -> List[PHIEntity]:
        """Remove NAME/ORGANIZATION entities that match the deny-lists.

        Args:
            entities: Detected PHI entities from all detectors.

        Returns:
            Entities with clinical-phrase and section-header NAME/ORG
            detections removed.
        """
        validated: List[PHIEntity] = []
        for entity in entities:
            if self._is_in_scope(entity) and not self._is_valid_name(entity):
                logger.debug(
                    "Name/Org drop: '%s' (category=%s)",
                    entity.text,
                    entity.category,
                )
            else:
                validated.append(entity)
        return validated

    def _is_in_scope(self, entity: PHIEntity) -> bool:
        """Return True when this entity should be evaluated by this filter.

        Args:
            entity: The entity to check.

        Returns:
            True for Presidio-sourced NAME or ORGANIZATION entities.
        """
        source = getattr(entity, "source", "unknown")
        return entity.category in _FILTERED_CATEGORIES and source in _PRESIDIO_SOURCES

    def _is_valid_name(self, entity: PHIEntity) -> bool:
        """Return True when the entity text looks like a real person/org name.

        Args:
            entity: The candidate NAME/ORGANIZATION entity.

        Returns:
            True when none of the deny-list checks fire.
        """
        text = entity.text.strip()
        if len(text) < _MIN_NAME_LENGTH:
            return False
        if "\n" in text:
            return False
        return not self._is_clinical_term(text) and not self._is_section_header(text)

    def _is_clinical_term(self, text: str) -> bool:
        """Return True when text is a known clinical term or phrase.

        Args:
            text: Stripped entity text.

        Returns:
            True when text appears in CLINICAL_TERMS or CLINICAL_PHRASES.
        """
        if text in RedactionConfig.CLINICAL_TERMS:
            return True
        return any(phrase in text for phrase in RedactionConfig.CLINICAL_PHRASES)

    def _is_section_header(self, text: str) -> bool:
        """Return True when text is a document section header.

        Args:
            text: Stripped entity text.

        Returns:
            True when text appears in COMMON_HEADERS or HEADER_PHRASES.
        """
        if text in RedactionConfig.COMMON_HEADERS:
            return True
        return any(phrase in text for phrase in RedactionConfig.HEADER_PHRASES)
