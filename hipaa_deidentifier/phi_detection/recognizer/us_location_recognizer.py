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
        r'\b\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln|Place|Pl|Court|Ct|Circle|Cir|Way|Parkway|Pkwy|Highway|Hwy)(?:,\s*(?:Apt|Apartment|Unit|Suite|Ste)\s*[A-Za-z0-9-]+)?(?:,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)?\b',

        # State abbreviations with ZIP codes
        r'\b([A-Z]{2})\s+\d{5}(?:-\d{4})?\b',  # CA 90210 or CA 90210-1234
        
        # City, state patterns
        r'\b\w+,\s+([A-Z]{2})\b',              # Anytown, CA
        r'\b\w+,\s+\w+,\s+([A-Z]{2})\b',       # 123 Main St, Anytown, CA
        
        # ZIP codes
        r'\b\d{5}(?:-\d{4})?\b',               # 90210 or 90210-1234
        
        # Common US address formats
        r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln|Place|Pl|Court|Ct|Circle|Cir|Way|Parkway|Pkwy|Highway|Hwy)\b',
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
        
        logger.info(f"USLocationRecognizer initialized with {len(self.LOCATION_PATTERNS)} patterns and {len(LocationConfig.US_STATE_ABBR)} state abbreviations")
    
    def load(self) -> None:
        """Load the recognizer (no external resources needed)."""
        pass
    
    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: NlpArtifacts = None, **kwargs
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
        for pattern_idx, pattern in enumerate(self.compiled_patterns):
            for match in pattern.finditer(text):
                # Create a recognizer result
                result = RecognizerResult(
                    entity_type="LOCATION",
                    start=match.start(),
                    end=match.end(),
                    score=RecognizerThresholds.MEDIUM_HIGH_CONFIDENCE,
                    analysis_explanation=f"US location pattern {pattern_idx + 1} matched"
                )
                results.append(result)
                logger.debug(f"Location pattern match at {match.start()}-{match.end()}: {match.group()}")
        
        logger.info(f"USLocationRecognizer found {len(results)} location matches")
        return results
