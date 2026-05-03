"""
Age Over 89 Recognizer — Detects ages exceeding the HIPAA Safe Harbor threshold.

Architecture:
-------------
    ┌─────────────────────────┐     ┌──────────────────────────┐
    │  PresidioIdentifier     │────▶│  AgeOver89Recognizer     │
    │  (identifier/)          │     │  (recognizer/)           │
    └─────────────────────────┘     └──────────────────────────┘

    Registered with Presidio's AnalyzerEngine registry.
    Fires on AGE_OVER_89 entity type.

    HIPAA Safe Harbor §164.514(b): ages over 89 must be generalised
    to a category (e.g. "90+") rather than the specific value.

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

logger = get_logger("recognizer.age_over_89")


class AgeOver89Recognizer(PatternRecognizer):
    """Recognizes patient ages that exceed the HIPAA Safe Harbor threshold of 89.

    Detects patterns such as:
    - Age: 92
    - 95 years old
    - (age 101)
    - Patient is 90 years of age

    Example:
        >>> recognizer = AgeOver89Recognizer()
        >>> results = recognizer.analyze("Patient aged 94", ["AGE_OVER_89"], None)
        >>> print(len(results))
        1
    """

    def __init__(
        self,
        name: str = "AGE_OVER_89",
        supported_entity: str = "AGE_OVER_89",
        patterns: Optional[List[Pattern]] = None,
    ) -> None:
        """Initialize the age-over-89 recognizer.

        Args:
            name: Recognizer name for Presidio registry.
            supported_entity: Entity type emitted on detection.
            patterns: Optional custom patterns; defaults are used when None.
        """
        if patterns is None:
            patterns = [
                Pattern(
                    "age_keyword_over_89",
                    r"\b(?:age|aged?)\s*[:\-=]?\s*(9[0-9]|1[0-9]{2,})\b",
                    RecognizerThresholds.VERY_HIGH_CONFIDENCE,
                ),
                Pattern(
                    "years_old_over_89",
                    r"\b(9[0-9]|1[0-9]{2,})[\s\-]*(?:years?[\s\-]*old|y\.?o\.?|years?\s*of\s*age)\b",
                    RecognizerThresholds.VERY_HIGH_CONFIDENCE,
                ),
                Pattern(
                    "age_in_parentheses_over_89",
                    r"\((?:age|aged?)?:?\s*(9[0-9]|1[0-9]{2,})\)",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                Pattern(
                    "age_with_subject_over_89",
                    r"(?:patient|individual|person|male|female|man|woman)\s+(?:is|aged?|of age)\s*(9[0-9]|1[0-9]{2,})",
                    RecognizerThresholds.MEDIUM_HIGH_CONFIDENCE,
                ),
                # Birth years that imply age > 89 based on HIPAA threshold year
                Pattern(
                    "birth_year_implying_over_89",
                    r"\b(?:born|birth|DOB|date of birth).*(?:18[0-9]{2}|19[0-2][0-9])\b",
                    RecognizerThresholds.MEDIUM_CONFIDENCE,
                ),
            ]

        super().__init__(
            supported_entity=supported_entity, patterns=patterns, name=name
        )
        logger.info("AgeOver89Recognizer initialized with %d patterns", len(patterns))
