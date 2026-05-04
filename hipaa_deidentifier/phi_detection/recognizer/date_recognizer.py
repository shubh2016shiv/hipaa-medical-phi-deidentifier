"""
Date Recognizer — Detects dates in the formats commonly found in medical records.

Architecture:
-------------
    ┌─────────────────────────┐     ┌──────────────────────────┐
    │  PresidioIdentifier     │────▶│  DateRecognizer          │
    │  (identifier/)          │     │  (recognizer/)           │
    └─────────────────────────┘     └──────────────────────────┘

    Registered with Presidio's AnalyzerEngine registry.
    Overrides Presidio's built-in date recognizer to extend coverage
    to clinical formats (DOB labels, date ranges, MM.DD.YYYY, etc.).

Dependencies:
    - recognizer_config.py  — DateConfig, RecognizerThresholds constants
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
from .recognizer_config import DateConfig, RecognizerThresholds

logger = get_logger("recognizer.date")


class DateRecognizer(EntityRecognizer):
    """Recognizes dates in various formats found in medical documents.

    Recognizes dates including:
    - Numeric: MM/DD/YYYY, YYYY-MM-DD, DD.MM.YYYY
    - Text month: January 1, 2023; 1st Jan 2023
    - With timestamps: MM/DD/YYYY HH:MM:SS
    - Clinical context: DOB: MM/DD/YYYY
    - Date ranges: MM/DD/YYYY to MM/DD/YYYY

    Example:
        >>> recognizer = DateRecognizer()
        >>> results = recognizer.analyze("DOB: 01/15/1980", ["DATE"], None)
        >>> print(len(results))
        1
    """

    DATE_PATTERNS: List[str] = [
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
        r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b",
        r"\b\d{4}\.\d{1,2}\.\d{1,2}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4}\b",
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*,?\s+\d{2,4}\b",
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\b",
        r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?\b",
        r"\(\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*\)",
        r"\(\s*\d{4}[/-]\d{1,2}[/-]\d{1,2}\s*\)",
        r"\b(?:DOB|Birth|Born):\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        r"\b(?:DOB|Birth|Born):\s*\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*(?:to|-)\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    ]

    def __init__(
        self,
        name: str = "DateRecognizer",
        supported_entities: List[str] | None = None,
        supported_language: str = "en",
        **kwargs,
    ) -> None:
        """Initialize the date recognizer with compiled patterns."""
        super().__init__(
            supported_entities=supported_entities or ["DATE"],
            supported_language=supported_language,
            name=name,
            **kwargs,
        )
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.DATE_PATTERNS
        ]
        logger.info(
            "DateRecognizer initialized with %d patterns", len(self.DATE_PATTERNS)
        )

    def load(self) -> None:
        """Load the recognizer (no external resources needed)."""

    def analyze(
        self,
        text: str,
        entities: List[str],
        nlp_artifacts: NlpArtifacts | None = None,
        **kwargs,
    ) -> List[RecognizerResult]:
        """Analyze text for date entities.

        Args:
            text: The text to analyze for date patterns.
            entities: Entity types to detect (must include "DATE").
            nlp_artifacts: NLP artifacts from spaCy (unused for pattern matching).

        Returns:
            List of RecognizerResult for each detected date.
        """
        results = []

        if "DATE" not in entities:
            logger.debug("DATE not in requested entities, skipping")
            return results

        for _, pattern in enumerate(self.compiled_patterns):
            for match in pattern.finditer(text):
                matched_text = match.group()
                if self._is_valid_date(matched_text):
                    results.append(
                        RecognizerResult(
                            entity_type="DATE",
                            start=match.start(),
                            end=match.end(),
                            score=RecognizerThresholds.VERY_HIGH_CONFIDENCE,
                        )
                    )
                    logger.debug(
                        "Date at %d-%d: %s", match.start(), match.end(), matched_text
                    )

        results = self._deduplicate_spans(results)
        logger.info("DateRecognizer found %d dates", len(results))
        return results

    @staticmethod
    def _deduplicate_spans(results: List[RecognizerResult]) -> List[RecognizerResult]:
        """Keep the longest span when multiple patterns match overlapping regions.

        Patterns 1+7 both fire on "03/15/2024 08:30 AM"; patterns 1+11 both fire
        on "DOB: 02/18/1965".  Sorting by start then by descending length and
        discarding any result fully contained within an already-kept result
        ensures each physical date produces exactly one entity.
        """
        if len(results) < 2:
            return results
        sorted_results = sorted(results, key=lambda r: (r.start, -(r.end - r.start)))
        deduped: List[RecognizerResult] = []
        for result in sorted_results:
            if not any(
                k.start <= result.start and k.end >= result.end for k in deduped
            ):
                deduped.append(result)
        return deduped

    def _is_valid_date(self, date_text: str) -> bool:
        """Validate detected text as a plausible date.

        Args:
            date_text: The candidate date string.

        Returns:
            True if the text passes basic date sanity checks.
        """
        if not re.search(r"\d", date_text):
            return False
        if len(date_text) < 6:
            return False
        year_match = re.search(r"\b(\d{4})\b", date_text)
        if year_match:
            year = int(year_match.group(1))
            if year < DateConfig.MIN_YEAR or year > DateConfig.MAX_YEAR:
                return False
        return True
