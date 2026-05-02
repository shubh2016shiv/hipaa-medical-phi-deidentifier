"""
SSN Recognizer — Detects US Social Security Numbers with format validation.

Architecture:
-------------
    ┌─────────────────────────┐     ┌──────────────────────────┐
    │  PresidioIdentifier     │────▶│  SSNRecognizer           │
    │  (identifier/)          │     │  (recognizer/)           │
    └─────────────────────────┘     └──────────────────────────┘

    Registered with Presidio's AnalyzerEngine registry.
    Overrides Presidio's built-in SSN recognizer to add validation rules
    that reject known-invalid area codes and suppress identifier suffixes
    (e.g. MRN or account numbers that happen to be 9 digits).

Dependencies:
    - recognizer_config.py  — SSNConfig, RecognizerThresholds constants
    - utils/logger.py       — Structured logging

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

import re
from typing import List

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from ...utils.logger import get_logger
from .recognizer_config import SSNConfig, RecognizerThresholds

logger = get_logger("recognizer.ssn")


class SSNRecognizer(EntityRecognizer):
    """Recognizes US Social Security Numbers with comprehensive validation.

    Supported formats:
    - Dashes:          123-45-6789
    - No separators:   123456789
    - Dot separators:  123.45.6789

    Validation rules (per SSA specification):
    - Area number cannot be 000, 666, or 900–999
    - Group number cannot be 00
    - Serial number cannot be 0000

    Example:
        >>> recognizer = SSNRecognizer()
        >>> results = recognizer.analyze("SSN: 123-45-6789", ["US_SSN"], None)
        >>> print(len(results))
        1
    """

    SSN_PATTERNS: List[str] = [
        r"\b(?!000|666|9\d{2})\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b",
        r"\b(?!000|666|9\d{2})\d{3}(?!00)\d{2}(?!0000)\d{4}\b",
        r"\b(?!000|666|9\d{2})\d{3}\.(?!00)\d{2}\.(?!0000)\d{4}\b",
    ]

    def __init__(
        self,
        name: str = "SSNRecognizer",
        supported_entities: List[str] | None = None,
        supported_language: str = "en",
        **kwargs,
    ) -> None:
        """Initialize the SSN recognizer with compiled patterns."""
        super().__init__(
            supported_entities=supported_entities or ["US_SSN", "SSN"],
            supported_language=supported_language,
            name=name,
            **kwargs,
        )
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.SSN_PATTERNS
        ]
        logger.info(
            "SSNRecognizer initialized with %d patterns", len(self.SSN_PATTERNS)
        )

    def load(self) -> None:
        """Load the recognizer (no external resources needed)."""

    def analyze(
        self,
        text: str,
        entities: List[str],
        nlp_artifacts: NlpArtifacts = None,
        **kwargs,
    ) -> List[RecognizerResult]:
        """Analyze text for SSN patterns.

        Args:
            text: The text to analyze for SSN patterns.
            entities: Entity types to detect (must include "US_SSN" or "SSN").
            nlp_artifacts: NLP artifacts from spaCy (unused for pattern matching).

        Returns:
            List of RecognizerResult for each detected SSN.
        """
        results = []

        if not any(entity in ["US_SSN", "SSN"] for entity in entities):
            logger.debug("SSN not in requested entities, skipping")
            return results

        for pattern_idx, pattern in enumerate(self.compiled_patterns):
            for match in pattern.finditer(text):
                matched_text = match.group()

                if self._is_identifier_suffix(text, match.start()):
                    logger.debug(
                        "SSN-like identifier suffix rejected: %s", matched_text
                    )
                    continue

                if self._is_valid_ssn(matched_text):
                    results.append(
                        RecognizerResult(
                            entity_type="US_SSN",
                            start=match.start(),
                            end=match.end(),
                            score=RecognizerThresholds.VERY_HIGH_CONFIDENCE,
                            analysis_explanation=f"SSN pattern {pattern_idx + 1} matched and validated",
                        )
                    )
                    logger.debug("Valid SSN at %d-%d", match.start(), match.end())
                else:
                    logger.debug("Invalid SSN rejected: %s", matched_text)

        logger.info("SSNRecognizer found %d SSNs", len(results))
        return results

    def _is_identifier_suffix(self, text: str, start: int) -> bool:
        """Check whether a 9-digit match is the numeric suffix of another identifier.

        Args:
            text: Full text being analyzed.
            start: Start offset of the candidate match.

        Returns:
            True when the candidate is attached to a known identifier prefix.
        """
        prefix_window = text[max(0, start - 12) : start]
        return bool(
            re.search(
                r"(?:FIN|ACC|ACCT|MRN|ENC|VST|ADM|PM|SN)[-#:\s]*$",
                prefix_window,
                re.IGNORECASE,
            )
        )

    def _is_valid_ssn(self, ssn_text: str) -> bool:
        """Validate a candidate SSN against SSA rules.

        Args:
            ssn_text: The candidate SSN string.

        Returns:
            True if all SSA validation rules pass.
        """
        clean_ssn = re.sub(r"[-.\s]", "", ssn_text)

        if not re.match(r"^\d{9}$", clean_ssn):
            return False

        area_number = clean_ssn[:3]
        if area_number in SSNConfig.INVALID_AREA_NUMBERS:
            return False
        if SSNConfig.is_invalid_area_prefix(area_number):
            return False

        if clean_ssn[3:5] == SSNConfig.INVALID_GROUP_NUMBER:
            return False

        if clean_ssn[5:9] == SSNConfig.INVALID_SERIAL_NUMBER:
            return False

        return True
