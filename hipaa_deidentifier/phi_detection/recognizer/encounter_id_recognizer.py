"""
Encounter ID Recognizer — Detects hospital visit and encounter identifiers.

Architecture:
-------------
    ┌─────────────────────────┐     ┌──────────────────────────┐
    │  PresidioIdentifier     │────▶│  EncounterIDRecognizer   │
    │  (identifier/)          │     │  (recognizer/)           │
    └─────────────────────────┘     └──────────────────────────┘

    Registered with Presidio's AnalyzerEngine registry.
    Fires on ENCOUNTER_ID entity type.

Dependencies:
    - recognizer_config.py  — RecognizerThresholds constants
    - utils/logger.py       — Structured logging

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

from typing import List, Optional

from presidio_analyzer import Pattern, PatternRecognizer

from ...utils.logger import get_logger
from .recognizer_config import RecognizerThresholds

logger = get_logger("recognizer.encounter_id")


class EncounterIDRecognizer(PatternRecognizer):
    """Recognizes hospital encounter and visit identifiers.

    Detects patterns such as:
    - Encounter ID: ENC-2024-001234
    - Visit Number: VST-98765
    - Admission ID: ADM-20231201-001

    Example:
        >>> recognizer = EncounterIDRecognizer()
        >>> results = recognizer.analyze("Encounter ID: ENC-2024-001234", ["ENCOUNTER_ID"], None)
        >>> print(len(results))
        1
    """

    def __init__(
        self,
        name: str = "ENCOUNTER_ID",
        supported_entity: str = "ENCOUNTER_ID",
        patterns: Optional[List[Pattern]] = None,
    ) -> None:
        """Initialize the encounter ID recognizer.

        Args:
            name: Recognizer name for Presidio registry.
            supported_entity: Entity type emitted on detection.
            patterns: Optional custom patterns; defaults are used when None.
        """
        if patterns is None:
            patterns = [
                Pattern(
                    "encounter_id_labeled",
                    r"\b(?:Encounter(?:\s*ID)?|Visit(?:\s*ID)?|Admission(?:\s*ID)?)\s*[:#=\-]?\s*([A-Z0-9\-]{6,18})\b",
                    RecognizerThresholds.VERY_HIGH_CONFIDENCE,
                ),
                Pattern(
                    "visit_number_labeled",
                    r"\bVisit\s*(?:Number|No\.?|#)\s*[:#=\-]?\s*([A-Z0-9\-]{6,18})\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                Pattern(
                    "encounter_id_prefixed",
                    r"\b(?:ENC|VST|ADM)[-]?([0-9]{6,12}(?:-[0-9]{1,4})?)\b",
                    RecognizerThresholds.MEDIUM_HIGH_CONFIDENCE,
                ),
                Pattern(
                    "encounter_id_date_based",
                    r"\bENC[-]?([0-9]{8}[-][0-9]{3,6})\b",
                    RecognizerThresholds.MEDIUM_CONFIDENCE,
                ),
            ]

        super().__init__(supported_entity=supported_entity, patterns=patterns, name=name)
        logger.info("EncounterIDRecognizer initialized with %d patterns", len(patterns))
