"""
US-specific Location Recognizer

This recognizer specifically targets US locations, including state abbreviations.
"""

import re
from typing import List, Optional

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts


class USLocationRecognizer(EntityRecognizer):
    """
    Custom recognizer for US-specific locations, including state abbreviations.
    """
    
    def __init__(self):
        """
        Initialize the US location recognizer.
        """
        super().__init__(
            supported_entities=["LOCATION"],
            supported_language="en",
            name="USLocationRecognizer"
        )
        
        # US state abbreviations
        self.us_states = {
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
            'DC', 'PR', 'VI', 'GU', 'AS', 'MP'
        }
        
        # Common US address patterns
        self.location_patterns = [
            # State abbreviations with context
            r'\b([A-Z]{2})\s+\d{5}(?:-\d{4})?\b',  # CA 90210 or CA 90210-1234
            r'\b\w+,\s+([A-Z]{2})\b',              # Anytown, CA
            r'\b\w+,\s+\w+,\s+([A-Z]{2})\b',       # 123 Main St, Anytown, CA
            
            # Zip codes
            r'\b\d{5}(?:-\d{4})?\b',               # 90210 or 90210-1234
            
            # Common address formats
            r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Lane|Ln|Place|Pl|Court|Ct|Circle|Cir|Way|Parkway|Pkwy|Highway|Hwy)\b',
        ]
        
        # Compile patterns
        self.compiled_patterns = [re.compile(pattern) for pattern in self.location_patterns]
    
    def load(self) -> None:
        """Load the recognizer (no external resources needed)."""
        pass
    
    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: NlpArtifacts
    ) -> List[RecognizerResult]:
        """
        Analyze text for US location entities.
        
        Args:
            text: The text to analyze
            entities: List of entity types to detect
            nlp_artifacts: NLP artifacts from the text
            
        Returns:
            List of RecognizerResult objects for detected locations
        """
        results = []
        
        # Only process if LOCATION is in the requested entities
        if "LOCATION" not in entities:
            return results
        
        # Find all pattern matches
        for pattern in self.compiled_patterns:
            for match in pattern.finditer(text):
                # Create a recognizer result
                result = RecognizerResult(
                    entity_type="LOCATION",
                    start=match.start(),
                    end=match.end(),
                    score=0.85,  # High confidence for pattern matches
                    analysis_explanation=f"US location pattern match: {match.group()}"
                )
                results.append(result)
        
        # Check for standalone state abbreviations - more aggressive approach
        for state in self.us_states:
            # Look for the state abbreviation with word boundaries
            pattern = r'\b' + state + r'\b'
            for match in re.finditer(pattern, text):
                # Create a recognizer result with high confidence
                result = RecognizerResult(
                    entity_type="LOCATION",
                    start=match.start(),
                    end=match.end(),
                    score=0.9,  # High confidence for state abbreviations
                    analysis_explanation=f"US state abbreviation: {match.group()}"
                )
                results.append(result)
        
        return results
