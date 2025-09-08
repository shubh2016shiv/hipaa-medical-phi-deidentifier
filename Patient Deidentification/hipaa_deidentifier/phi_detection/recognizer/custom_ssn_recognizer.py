"""
Custom SSN Recognizer

A custom recognizer specifically for US Social Security Numbers to ensure proper detection.
"""

import re
from typing import List, Optional

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts


class CustomSSNRecognizer(EntityRecognizer):
    """
    Custom recognizer for US Social Security Numbers.
    
    This recognizer ensures that SSNs in various formats are properly detected.
    """
    
    def __init__(self):
        """
        Initialize the custom SSN recognizer.
        """
        super().__init__(
            supported_entities=["US_SSN", "SSN"],
            supported_language="en",
            name="CustomSSNRecognizer"
        )
        
        # SSN patterns - more comprehensive than Presidio's default
        self.ssn_patterns = [
            # Standard format: 123-45-6789
            r'\b(?!000|666|9\d{2})\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b',
            # Without separators: 123456789
            r'\b(?!000|666|9\d{2})\d{3}(?!00)\d{2}(?!0000)\d{4}\b',
            # With dots: 123.45.6789
            r'\b(?!000|666|9\d{2})\d{3}\.(?!00)\d{2}\.(?!0000)\d{4}\b',
        ]
        
        # Compile patterns for efficiency
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.ssn_patterns]
    
    def load(self) -> None:
        """Load the recognizer (no external resources needed)."""
        pass
    
    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: NlpArtifacts
    ) -> List[RecognizerResult]:
        """
        Analyze text for SSN patterns.
        
        Args:
            text: The text to analyze
            entities: List of entity types to look for
            nlp_artifacts: NLP artifacts (not used for pattern matching)
            
        Returns:
            List of recognized SSN entities
        """
        results = []
        
        # Check if we should look for SSN entities
        if not any(entity in ["US_SSN", "SSN"] for entity in entities):
            return results
        
        # Search for SSN patterns
        for pattern in self.compiled_patterns:
            matches = pattern.finditer(text)
            
            for match in matches:
                # Extract the matched text
                matched_text = match.group()
                
                # Additional validation
                if self._is_valid_ssn(matched_text):
                    result = RecognizerResult(
                        entity_type="US_SSN",
                        start=match.start(),
                        end=match.end(),
                        score=0.95,  # High confidence for SSN detection
                        analysis_explanation=f"SSN pattern matched: {matched_text}"
                    )
                    results.append(result)
        
        return results
    
    def _is_valid_ssn(self, ssn_text: str) -> bool:
        """
        Validate that the detected text is a valid SSN format.
        
        Args:
            ssn_text: The text to validate
            
        Returns:
            True if the text appears to be a valid SSN
        """
        # Remove separators for validation
        clean_ssn = re.sub(r'[-.\s]', '', ssn_text)
        
        # Must be exactly 9 digits
        if not re.match(r'^\d{9}$', clean_ssn):
            return False
        
        # Check for invalid SSN patterns
        # Area numbers 000, 666, and 900-999 are invalid
        area_number = clean_ssn[:3]
        if area_number in ['000', '666'] or area_number.startswith('9'):
            return False
        
        # Group numbers 00 are invalid
        group_number = clean_ssn[3:5]
        if group_number == '00':
            return False
        
        # Serial numbers 0000 are invalid
        serial_number = clean_ssn[5:9]
        if serial_number == '0000':
            return False
        
        return True
