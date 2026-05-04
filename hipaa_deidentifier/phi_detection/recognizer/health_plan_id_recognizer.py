"""
Health Plan ID Recognizer — Detects health plan beneficiary numbers.

Architecture:
-------------
    ┌─────────────────────────┐     ┌──────────────────────────────┐
    │  PresidioIdentifier     │────▶│  HealthPlanIDRecognizer      │
    │  (identifier/)          │     │  (recognizer/)               │
    └─────────────────────────┘     └──────────────────────────────┘

    Registered with Presidio's AnalyzerEngine registry.
    Fires on HEALTH_PLAN_ID entity type.

    Covers HIPAA Safe Harbor identifier #6: health plan beneficiary numbers.

Dependencies:
    - recognizer_config.py  — RecognizerThresholds, IdentifierConfig constants
    - utils/logger.py       — Structured logging

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

from typing import List, Optional

from presidio_analyzer import Pattern, PatternRecognizer

from ...utils.logger import get_logger
from .recognizer_config import RecognizerThresholds

logger = get_logger("recognizer.health_plan_id")


class HealthPlanIDRecognizer(PatternRecognizer):
    """Recognizes health plan beneficiary numbers.

    Detects patterns such as:
    - Health Plan ID: BCBS-ABC123456
    - Member ID: UHC-987654
    - Insurance ID: AETNA-XYZ789

    Example:
        >>> recognizer = HealthPlanIDRecognizer()
        >>> results = recognizer.analyze("Member ID: BCBS-ABC123456", ["HEALTH_PLAN_ID"], None)
        >>> print(len(results))
        1
    """

    def __init__(
        self,
        name: str = "HEALTH_PLAN_ID",
        supported_entity: str = "HEALTH_PLAN_ID",
        patterns: Optional[List[Pattern]] = None,
    ) -> None:
        """Initialize the health plan ID recognizer.

        Args:
            name: Recognizer name for Presidio registry.
            supported_entity: Entity type emitted on detection.
            patterns: Optional custom patterns; defaults are used when None.
        """
        if patterns is None:
            patterns = [
                Pattern(
                    "health_plan_id_labeled",
                    r"\b(?:Health\s*Plan(?:\s*ID)?|Insurance(?:\s*ID)?|Member(?:\s*ID)?)\s*[:#=\-]?\s*([A-Z0-9\-]{6,20})\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                Pattern(
                    "health_plan_id_insurer_prefixed",
                    r"\b(?:BCBS|UHC|AETNA|CIGNA|HUMANA|ANTHEM)[\-]([A-Z0-9\-]{6,12})\b",
                    RecognizerThresholds.MEDIUM_HIGH_CONFIDENCE,
                ),
                Pattern(
                    "member_id_labeled",
                    r"\bMember\s*(?:ID|Number|#)?\s*[:#=\-]?\s*([A-Z0-9\-]{6,20})\b",
                    RecognizerThresholds.MEDIUM_CONFIDENCE,
                ),
                # Insurance group number — appears as "Group Number: GRP-987654"
                Pattern(
                    "group_number_labeled",
                    r"\bGroup\s*(?:Number|No\.?|ID|#)?\s*[:#=\-]?\s*([A-Z0-9\-]{4,15})\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                # Medicare Beneficiary Identifier (MBI) — 11-char alphanumeric format
                # introduced 2018: digit, char, char/digit, char, char/digit, digit,
                # char, char/digit, digit, char, char (e.g. 1EG4-TE5-MK72)
                Pattern(
                    "medicare_mbi",
                    r"\b[1-9][A-CEGHJ-NP-RT-Y][A-CEGHJ-NP-RT-Y0-9]\d[A-CEGHJ-NP-RT-Y][A-CEGHJ-NP-RT-Y0-9]\d[A-CEGHJ-NP-RT-Y]{2}\d{2}\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                # Medicare Number labeled — catches "Medicare Number: 1EG4-TE5-MK72"
                Pattern(
                    "medicare_number_labeled",
                    r"\bMedicare\s*(?:Number|No\.?|ID|Beneficiary\s*ID|#)?\s*[:#=\-]?\s*([A-Z0-9\-]{8,15})\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                # Medicaid member ID labeled
                Pattern(
                    "medicaid_id_labeled",
                    r"\bMedicaid\s*(?:Number|No\.?|ID|#)?\s*[:#=\-]?\s*([A-Z0-9\-]{6,15})\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
            ]

        super().__init__(
            supported_entity=supported_entity, patterns=patterns, name=name
        )
        logger.info(
            "HealthPlanIDRecognizer initialized with %d patterns", len(patterns)
        )
