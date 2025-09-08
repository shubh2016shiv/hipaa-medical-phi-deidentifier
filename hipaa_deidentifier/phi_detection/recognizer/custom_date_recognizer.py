"""
Custom Date Recognizer

A custom recognizer specifically for dates to ensure proper detection and categorization.
"""

import re
from typing import List, Optional

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts


class CustomDateRecognizer(EntityRecognizer):
    """
    Custom recognizer for dates in various formats.
    
    This recognizer ensures that dates are properly detected and categorized as DATE entities.
    """
    
    def __init__(self):
        """
        Initialize the custom date recognizer.
        """
        super().__init__(
            supported_entities=["DATE"],
            supported_language="en",
            name="CustomDateRecognizer"
        )
        
        # Date patterns - comprehensive coverage
        self.date_patterns = [
            # Numeric date formats
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # MM/DD/YYYY or DD/MM/YYYY
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',    # YYYY-MM-DD
            r'\b\d{1,2}\.\d{1,2}\.\d{2,4}\b',      # MM.DD.YYYY or DD.MM.YYYY
            r'\b\d{4}\.\d{1,2}\.\d{1,2}\b',        # YYYY.MM.DD
            
            # Text month formats
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4}\b',  # Month DD, YYYY
            r'\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*,?\s+\d{2,4}\b',  # DD Month YYYY
            
            # Formats with time components
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\b',  # MM/DD/YYYY HH:MM(:SS) (AM/PM)
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?\b',                 # YYYY-MM-DD HH:MM(:SS)
            
            # Dates in parentheses or brackets
            r'\(\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*\)',  # (MM/DD/YYYY)
            r'\(\s*\d{4}[/-]\d{1,2}[/-]\d{1,2}\s*\)',    # (YYYY-MM-DD)
            
            # Standalone years (for DOB contexts)
            r'\b(?:DOB|Birth|Born):\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',  # DOB: MM/DD/YYYY
            r'\b(?:DOB|Birth|Born):\s*\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',    # DOB: YYYY-MM-DD
        ]
        
        # Compile patterns for efficiency
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.date_patterns]
    
    def load(self) -> None:
        """Load the recognizer (no external resources needed)."""
        pass
    
    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: NlpArtifacts
    ) -> List[RecognizerResult]:
        """
        Analyze text for date entities.
        
        Args:
            text: The text to analyze
            entities: List of entity types to detect
            nlp_artifacts: NLP artifacts from the text
            
        Returns:
            List of RecognizerResult objects for detected dates
        """
        results = []
        
        # Only process if DATE is in the requested entities
        if "DATE" not in entities:
            return results
        
        # Find all date matches
        for pattern in self.compiled_patterns:
            for match in pattern.finditer(text):
                # Create a recognizer result
                result = RecognizerResult(
                    entity_type="DATE",
                    start=match.start(),
                    end=match.end(),
                    score=0.95,  # High confidence for date patterns
                    analysis_explanation=f"Date pattern match: {match.group()}"
                )
                results.append(result)
        
        return results
