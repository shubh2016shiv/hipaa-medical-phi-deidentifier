"""
Enhanced Fax Number Recognizer for US Healthcare Data

This recognizer specifically targets US-format fax numbers in medical documents.
"""

import re
from typing import List, Optional
from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

class EnhancedFaxRecognizer(EntityRecognizer):
    """
    Recognizes US-format fax numbers in medical documents.
    
    This recognizer looks for fax numbers in common formats, especially when
    preceded by "fax", "facsimile", "fax #", etc.
    """
    
    def __init__(self):
        """Initialize the recognizer with US fax number patterns."""
        super().__init__(
            supported_entities=["FAX_NUMBER"],
            supported_language="en",
            name="EnhancedFaxRecognizer"
        )
        
        # US-specific fax number patterns
        self.fax_patterns = [
            # Patterns with "fax" context
            r'\bfax(?:\s+(?:number|no|#|:))?\s*(?:\:|\-)?\s*((?:\+?1\s*[-\.]?)?\(?[0-9]{3}\)?[-\.\s]?[0-9]{3}[-\.\s]?[0-9]{4})',
            r'\bfacsimile(?:\s+(?:number|no|#|:))?\s*(?:\:|\-)?\s*((?:\+?1\s*[-\.]?)?\(?[0-9]{3}\)?[-\.\s]?[0-9]{3}[-\.\s]?[0-9]{4})',
            # Labeled fax numbers
            r'\b(?:fax|facsimile)(?:\s+(?:number|no|#|:))?\s*(?:\:|\-)?\s*(.+?)(?:\s|$)',
            # Fax in context
            r'(?:send|transmit|receive)(?:\s+(?:via|by))?\s+fax(?:\s+(?:to|at|:))?\s*(?:\:|\-)?\s*(.+?)(?:\s|$)',
            r'(?:fax|facsimile)(?:\s+(?:results|records|documents))?\s+(?:to|at|:)\s*(?:\:|\-)?\s*(.+?)(?:\s|$)',
        ]
        
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.fax_patterns]
        
    def load(self) -> None:
        """No loading needed."""
        pass
        
    def analyze(self, text: str, entities: List[str], nlp_artifacts: NlpArtifacts) -> List[RecognizerResult]:
        """
        Analyze text to find US-format fax numbers.
        
        Args:
            text: The text to analyze
            entities: List of entities to look for
            nlp_artifacts: NLP artifacts from the NLP engine
            
        Returns:
            List of RecognizerResult objects
        """
        results = []
        if "FAX_NUMBER" not in entities:
            return results
            
        # Check each pattern
        for pattern in self.compiled_patterns:
            for match in pattern.finditer(text):
                # Get the full match and the fax number group
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
                
                # Only consider it a fax if "fax" or "facsimile" is in context
                if "fax" in full_match.lower() or "facsimile" in full_match.lower():
                    results.append(
                        RecognizerResult(
                            entity_type="FAX_NUMBER",
                            start=start,
                            end=end,
                            score=0.85,  # High confidence when "fax" is explicitly mentioned
                            analysis_explanation=f"Fax number detected: {fax_number}"
                        )
                    )
                    
        return results