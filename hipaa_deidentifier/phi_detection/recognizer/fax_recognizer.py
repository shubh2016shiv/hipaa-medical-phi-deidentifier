"""
Enhanced Fax Number Recognizer

Specialized recognizer for US fax numbers in medical documents.
Requires fax context labels to distinguish from regular phone numbers.

Enterprise Features:
- Context-aware detection (requires "fax" label)
- Multiple US phone number formats
- High confidence scoring
- Professional logging

Author: HIPAA De-identification System
Version: 2.0.0 (Refactored for enterprise standards)
"""

import re
from typing import List

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from ...utils.logger import get_logger
from .recognizer_config import PhoneConfig, RecognizerThresholds

# Initialize module logger
logger = get_logger("recognizer.fax")


class FaxRecognizer(EntityRecognizer):
    """
    Recognizes US-format fax numbers in medical documents.

    Key Feature: Only detects numbers explicitly labeled as fax numbers
    to avoid false positives with regular phone numbers.

    Supported Formats:
    - Fax: (555) 123-4567
    - Fax: 555-123-4567
    - Fax: 555.123.4567
    - Facsimile: +1-555-123-4567

    Context Requirements:
    - Must include "fax" or "facsimile" keywords in proximity
    - Prevents misclassification of regular phone numbers
    """

    # Fax-specific pattern definitions
    FAX_PATTERNS: List[str] = [
        # Patterns with "fax" context - most common
        r"\bfax(?:\s+(?:number|no|#|:))?\s*(?:\:|\-)?\s*((?:\+?1\s*[-\.]?)?\(?[0-9]{3}\)?[-\.\s]?[0-9]{3}[-\.\s]?[0-9]{4})",
        r"\bfacsimile(?:\s+(?:number|no|#|:))?\s*(?:\:|\-)?\s*((?:\+?1\s*[-\.]?)?\(?[0-9]{3}\)?[-\.\s]?[0-9]{3}[-\.\s]?[0-9]{4})",
        # Labeled fax numbers
        r"\b(?:fax|facsimile)(?:\s+(?:number|no|#|:))?\s*(?:\:|\-)?\s*(.+?)(?:\s|$)",
        # Fax in action context
        r"(?:send|transmit|receive)(?:\s+(?:via|by))?\s+fax(?:\s+(?:to|at|:))?\s*(?:\:|\-)?\s*(.+?)(?:\s|$)",
        r"(?:fax|facsimile)(?:\s+(?:results|records|documents))?\s+(?:to|at|:)\s*(?:\:|\-)?\s*(.+?)(?:\s|$)",
    ]

    def __init__(
        self,
        name: str = "FaxRecognizer",
        supported_entities: List[str] | None = None,
        supported_language: str = "en",
        **kwargs,
    ):
        """Initialize the fax recognizer with context-aware patterns."""
        super().__init__(
            supported_entities=supported_entities or ["FAX_NUMBER"],
            supported_language=supported_language,
            name=name,
            **kwargs,
        )

        # Compile patterns for efficiency
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.FAX_PATTERNS
        ]

        logger.info(f"FaxRecognizer initialized with {len(self.FAX_PATTERNS)} patterns")

    def load(self) -> None:
        """Load the recognizer (no external resources needed)."""
        pass

    def analyze(
        self,
        text: str,
        entities: List[str],
        nlp_artifacts: NlpArtifacts | None = None,
        **kwargs,
    ) -> List[RecognizerResult]:
        """
        Analyze text to find US-format fax numbers.

        Args:
            text: The text to analyze for fax numbers
            entities: List of entity types to detect (must include "FAX_NUMBER")
            nlp_artifacts: NLP artifacts from spaCy (not used for pattern matching)

        Returns:
            List of RecognizerResult objects for detected fax numbers

        Example:
            >>> recognizer = FaxRecognizer()
            >>> results = recognizer.analyze("Fax: (555) 123-4567", ["FAX_NUMBER"], None)
            >>> print(len(results))
            1
        """
        results = []

        if "FAX_NUMBER" not in entities:
            logger.debug("FAX_NUMBER not in requested entities, skipping")
            return results

        # Check each pattern
        for _, pattern in enumerate(self.compiled_patterns):
            for match in pattern.finditer(text):
                # Get the full match and extract fax number
                full_match = match.group(0)

                # If there's a capturing group, use it; otherwise use the full match
                if len(match.groups()) > 0:
                    fax_number = match.group(1)
                    start = match.start(1)
                    end = match.end(1)
                else:
                    fax_number = full_match
                    start = match.start()
                    end = match.end()

                # Only consider it a fax if "fax" or "facsimile" is explicitly in context
                if self._has_fax_context(full_match):
                    result = RecognizerResult(
                        entity_type="FAX_NUMBER",
                        start=start,
                        end=end,
                        score=RecognizerThresholds.MEDIUM_HIGH_CONFIDENCE,
                    )
                    results.append(result)
                    logger.debug(f"Fax number detected at {start}-{end}: {fax_number}")
                else:
                    logger.debug(f"Match rejected (no fax context): {full_match}")

        logger.info(f"FaxRecognizer found {len(results)} fax numbers")
        return results

    def _has_fax_context(self, text: str) -> bool:
        """
        Check if the matched text has fax-related context.

        Args:
            text: The matched text to check for fax context

        Returns:
            True if the text contains fax-related keywords, False otherwise
        """
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in PhoneConfig.FAX_KEYWORDS)
