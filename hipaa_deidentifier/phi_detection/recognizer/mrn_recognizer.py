"""
Enhanced MRN Recognizer

A specialized recognizer for Medical Record Numbers (MRNs) in various hospital formats.
Supports multiple US healthcare system MRN patterns.

Enterprise Features:
- Comprehensive MRN pattern coverage
- Context-aware detection
- Configurable confidence thresholds
- Professional logging

Author: HIPAA De-identification System
Version: 2.0.0 (Refactored for enterprise standards)
"""

import re
from typing import List

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from ...utils.logger import get_logger
from .recognizer_config import MRNConfig, RecognizerThresholds

# Initialize module logger
logger = get_logger("recognizer.mrn")


class MRNRecognizer(EntityRecognizer):
    """
    Custom recognizer for Medical Record Numbers (MRNs) in various formats.

    Recognizes MRNs across multiple US healthcare system formats including:
    - Prefixed formats: MR-2024-001234, MRN-ABC-123
    - State-based: MRN-AZ-44-22119
    - Institution-specific: BGH-0099-7766
    - Numeric: 8-9 digit identifiers
    - Context-based: "Medical Record #: 987654321"

    Features:
    - Pattern-based matching with high confidence
    - Context keyword detection
    - Length validation
    - Professional logging
    """
    
    # MRN pattern definitions
    MRN_PATTERNS: List[str] = [
        # Common MRN formats with prefixes
        r'MR-\d+-\d+',                   # MR-2024-001234
        r'MRN[\s:]*\d+',                 # MRN: 12345678
        r'MRN-[A-Z]+-\d+',               # MRN-ABC-123
        r'[A-Z]+-[A-Z]+-\d+',            # ABC-DEF-123
        r'MRN-[A-Z]+-\d+-\d+',           # MRN-ABC-123-456
        
        # US hospital-specific MRN formats
        r'MRN[\s:]*[A-Z]{1,3}-[A-Z]{1,3}-\d{2,}-\d{4,}',  # MRN: MRN-AZ-44-22119
        r'MRN[\s:]*[A-Z]{2,}-\d{4,}',                     # MRN: BGH-0099-7766
        
        # Labeled MRN with various formats
        r'Medical Record #?:?\s*\d+',    # Medical Record #: 987654321
        r'Patient ID[\s:]*\d{6,12}',     # Patient ID: 123456789
        r'Chart #?[\s:]*\d{6,12}',       # Chart #: 123456789
        r'Patient Number[\s:]*\d{6,12}', # Patient Number: 123456789
        
        # Standalone numeric MRNs (common in US hospitals)
        r'\b\d{8}\b',                    # 8-digit MRN
        r'\b\d{9}\b',                    # 9-digit MRN
        
        # MRN with explicit label and flexible format
        r'MRN:?\s*MR-\d+-\d+',           # MRN: MR-2024-001234
        r'MRN:?\s*MR\s*-\s*\d+\s*-\s*\d+', # MRN: MR - 2024 - 001234 (with spaces)
        
        # Context-based MRN detection
        r'Medical\s+record\s+numbers?:?\s*.+?(?=\n|$)',  # Capture line after "Medical record number:"
        r'MRN:?\s*.+?(?=\n|$)',                          # Capture line after "MRN:"
    ]
    
    def __init__(
        self,
        name: str = "MRNRecognizer",
        supported_entities: List[str] | None = None,
        supported_language: str = "en",
        **kwargs,
    ):
        """Initialize the enhanced MRN recognizer with comprehensive patterns."""
        super().__init__(
            supported_entities=supported_entities or ["MRN"],
            supported_language=supported_language,
            name=name,
            **kwargs,
        )
        
        # Compile patterns for efficiency
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.MRN_PATTERNS
        ]
        
        logger.info(f"MRNRecognizer initialized with {len(self.MRN_PATTERNS)} patterns")
    
    def load(self) -> None:
        """Load the recognizer (no external resources needed)."""
        pass
    
    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: NlpArtifacts = None, **kwargs
    ) -> List[RecognizerResult]:
        """
        Analyze text for MRN entities.
        
        Args:
            text: The text to analyze for MRN patterns
            entities: List of entity types to detect (must include "MRN")
            nlp_artifacts: NLP artifacts from spaCy (not used for pattern matching)
            
        Returns:
            List of RecognizerResult objects for detected MRNs
            
        Example:
            >>> recognizer = MRNRecognizer()
            >>> results = recognizer.analyze("MRN: MR-2024-001234", ["MRN"], None)
            >>> print(len(results))
            1
        """
        results = []
        
        # Only process if MRN is in the requested entities
        if "MRN" not in entities:
            logger.debug("MRN not in requested entities, skipping")
            return results
        
        # Find all MRN matches
        for pattern_idx, pattern in enumerate(self.compiled_patterns):
            for match in pattern.finditer(text):
                # Validate the match
                matched_text = match.group()
                
                if self._is_valid_mrn(matched_text):
                    # Create a recognizer result
                    result = RecognizerResult(
                        entity_type="MRN",
                        start=match.start(),
                        end=match.end(),
                        score=RecognizerThresholds.VERY_HIGH_CONFIDENCE,
                        analysis_explanation=f"MRN pattern {pattern_idx + 1} matched"
                    )
                    results.append(result)
                    logger.debug(f"Valid MRN detected at position {match.start()}-{match.end()}: {matched_text}")
                else:
                    logger.debug(f"Invalid MRN format rejected: {matched_text}")
        
        logger.info(f"MRNRecognizer found {len(results)} valid MRNs")
        return results
    
    def _is_valid_mrn(self, mrn_text: str) -> bool:
        """
        Validate that the detected text is a valid MRN format.
        
        Validation rules:
        - Must meet minimum length requirements
        - Must not exceed maximum length
        - Should contain digits or alphanumeric patterns
        
        Args:
            mrn_text: The text to validate as an MRN
            
        Returns:
            True if the text appears to be a valid MRN, False otherwise
        """
        # Check minimum length
        if len(mrn_text) < MRNConfig.MIN_MRN_LENGTH:
            return False
        
        # Check maximum length
        if len(mrn_text) > MRNConfig.MAX_MRN_LENGTH:
            return False
        
        # Must contain at least one digit
        if not re.search(r'\d', mrn_text):
            return False
        
        return True
