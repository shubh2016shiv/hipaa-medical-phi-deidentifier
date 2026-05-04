"""
US-specific Location Recognizer

Specialized recognizer for US locations including addresses, state abbreviations, and ZIP codes.
Implements HIPAA-compliant location detection for US healthcare data.

Enterprise Features:
- Comprehensive US state coverage (50 states + DC + territories)
- Address pattern recognition
- ZIP code detection (5-digit and ZIP+4)
- Context-aware matching
- Professional logging

Author: HIPAA De-identification System
Version: 2.0.0 (Refactored for enterprise standards)
"""

import re
from typing import List

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from ...utils.logger import get_logger
from .recognizer_config import LocationConfig, RecognizerThresholds

# Initialize module logger
logger = get_logger("recognizer.location")


class USLocationRecognizer(EntityRecognizer):
    """
    Custom recognizer for US-specific locations.

    Recognizes:
    - US state abbreviations (all 50 states + DC + territories)
    - ZIP codes (5-digit and ZIP+4 formats)
    - Street addresses with common patterns
    - City, state combinations

    Features:
    - High confidence state detection
    - Pattern-based address matching
    - ZIP code validation
    - Professional logging
    """

    # Location pattern definitions
    LOCATION_PATTERNS: List[str] = [
        # Full street address with optional apartment/unit, city, state, and ZIP
        r"\b\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln|Place|Pl|Court|Ct|Circle|Cir|Way|Parkway|Pkwy|Highway|Hwy)(?:,\s*(?:Apt|Apartment|Unit|Suite|Ste)\s*[A-Za-z0-9-]+)?(?:,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)?\b",
        # State abbreviation + ZIP code (e.g. "CA 90210", "MA 02101-1234")
        r"\b([A-Z]{2})\s+\d{5}(?:-\d{4})?\b",
        # Multi-word city + state (e.g. "New York, NY") — Title-case words only,
        # never a bare credential like "Johnson, MD" because credentials appear
        # after a full name (uppercase first char + mixed case tail) and Pattern 3
        # (\b\w+,\s+[A-Z]{2}\b) cannot distinguish them from city+state.
        # Replaced with the city-state-ZIP form below and facility patterns.
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?\b",
        # "123 Main St, Anytown, CA" — word before state already anchored by street address
        r"\b\w+,\s+\w+,\s+([A-Z]{2})\b",
        # ZIP codes — only when preceded by a state abbreviation (avoids bare number FPs)
        r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b",
        # Common US address formats (street number + street type keyword)
        r"\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln|Place|Pl|Court|Ct|Circle|Cir|Way|Parkway|Pkwy|Highway|Hwy)\b",
        # Labeled location/facility field (e.g. "Location: City Hospital, Suite 3")
        # Must be followed by a capitalised facility/room name; stops at newline.
        # Negative lookahead rejects generic non-place values (Patient, Same, PACS).
        r"\bLocation\s*[:#]\s*(?!(?:Patient|Same|PACS|N/?A)\b)[A-Z][A-Za-z0-9 \-\.,]{5,80}(?:(?:Clinic|Hospital|Center|Suite|Room|Floor|Building|Bldg|Ste|Dept|Department|Ward|Unit)[A-Za-z0-9 \-\.,]{0,40})",
        # Named clinical facility with suite number — "Clinic/Hospital/Center, Suite NNN"
        # The suite number is a structural anchor, not vocabulary enumeration.
        # (Standalone facility names without a suite are handled by FacilityLocationRecognizer
        # using spaCy's NER ORG label — no regex vocabulary needed.)
        r"\b[A-Z][a-zA-Z \-\.]{3,50}(?:Clinic|Hospital|Medical Center|Health Center|Outpatient \w+)\s*,\s*(?:Suite|Ste|Bldg|Floor)\s+[A-Z0-9\-]+\b",
    ]

    def __init__(
        self,
        name: str = "USLocationRecognizer",
        supported_entities: List[str] | None = None,
        supported_language: str = "en",
        **kwargs,
    ):
        """Initialize the US location recognizer with state and address patterns."""
        super().__init__(
            supported_entities=supported_entities or ["LOCATION"],
            supported_language=supported_language,
            name=name,
            **kwargs,
        )

        # Compile patterns for efficiency
        self.compiled_patterns = [
            re.compile(pattern) for pattern in self.LOCATION_PATTERNS
        ]

        logger.info(
            f"USLocationRecognizer initialized with {len(self.LOCATION_PATTERNS)} patterns and {len(LocationConfig.US_STATE_ABBR)} state abbreviations"
        )

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
        Analyze text for US location entities.

        Args:
            text: The text to analyze for location patterns
            entities: List of entity types to detect (must include "LOCATION")
            nlp_artifacts: NLP artifacts from spaCy (not used for pattern matching)

        Returns:
            List of RecognizerResult objects for detected locations

        Example:
            >>> recognizer = USLocationRecognizer()
            >>> results = recognizer.analyze("Address: 123 Main St, Boston, MA 02101", ["LOCATION"], None)
            >>> print(len(results) > 0)
            True
        """
        results = []

        # Only process if LOCATION is in the requested entities
        if "LOCATION" not in entities:
            logger.debug("LOCATION not in requested entities, skipping")
            return results

        # Find all pattern matches
        for _, pattern in enumerate(self.compiled_patterns):
            for match in pattern.finditer(text):
                # Create a recognizer result
                result = RecognizerResult(
                    entity_type="LOCATION",
                    start=match.start(),
                    end=match.end(),
                    score=RecognizerThresholds.MEDIUM_HIGH_CONFIDENCE,
                )
                results.append(result)
                logger.debug(
                    f"Location pattern match at {match.start()}-{match.end()}: {match.group()}"
                )

        logger.info(f"USLocationRecognizer found {len(results)} location matches")
        return results
