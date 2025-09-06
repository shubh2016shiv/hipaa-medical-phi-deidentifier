"""
PHI Redaction Module

Implements various strategies for redacting or transforming detected PHI.
"""
import os
from typing import Dict, List

from ..models.phi_entity import PHIEntity
from ..utils.security import generate_secure_hash, get_salt_from_config
from ..utils.date_shifter import shift_date, get_date_shift_days_from_config


class PHIRedactor:
    """
    Applies redaction and transformation strategies to detected PHI.
    """
    
    def __init__(self, config: Dict):
        """
        Initializes the redactor with the specified configuration.
        
        Args:
            config: Configuration dictionary with redaction rules
        """
        self.config = config
        self.salt = get_salt_from_config(self.config)
        self.date_shift_days = get_date_shift_days_from_config(self.config)
        
    def redact_text(self, text: str, entities: List[PHIEntity]) -> str:
        """
        Redacts or transforms PHI entities in the text.
        
        Args:
            text: The original text containing PHI
            entities: List of detected PHI entities
            
        Returns:
            The text with PHI redacted or transformed
        """
        # Sort entities in reverse order (right to left)
        # This preserves the offsets as we make replacements
        sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)
        
        # Make a copy of the text that we'll modify
        redacted_text = text
        
        # Apply transformations
        for entity in sorted_entities:
            # Get the original text of the entity
            original_text = text[entity.start:entity.end]
            
            # Apply the appropriate transformation
            replacement = self._apply_transformation(entity.category, original_text)
            
            # Replace the entity in the text
            redacted_text = (
                redacted_text[:entity.start] + 
                replacement + 
                redacted_text[entity.end:]
            )
            
        return redacted_text
    
    def _apply_transformation(self, category: str, text: str) -> str:
        """
        Applies the appropriate transformation to a PHI entity.
        
        Args:
            category: The category of PHI
            text: The text to transform
            
        Returns:
            The transformed text
        """
        # Get the rule for this category, or use the default
        rules = self.config.get("transform", {}).get("rules", {})
        rule = rules.get(category, self.config.get("transform", {}).get("default_action", "redact"))
        
        # Apply the appropriate transformation
        if rule == "redact":
            return f"[REDACTED:{category}]"
            
        elif rule == "hash":
            # Generate a hash code (using more secure length)
            code = generate_secure_hash(text, self.salt, length=8)
            
            # Format according to configuration
            format_template = (
                self.config.get("hash_formats", {}).get(category) or 
                self.config.get("hash_formats", {}).get("DEFAULT") or 
                "{code}"
            )
            return format_template.format(code=code)
            
        elif rule == "pseudonym":
            # Generate a hash code for pseudonyms (shorter but still secure)
            code = generate_secure_hash(text, self.salt, length=6)
            
            # Format according to configuration
            format_template = (
                self.config.get("pseudonym_formats", {}).get(category) or 
                self.config.get("pseudonym_formats", {}).get("DEFAULT") or 
                "{code}"
            )
            return format_template.format(code=code)
            
        elif rule == "generalize":
            if category == "ZIP":
                # Keep only first 3 digits of ZIP code
                code = generate_secure_hash(text, self.salt, length=4)
                return f"ZIP_{code}"
            elif category == "AGE_OVER_89":
                return "AGE_OVER_89"
            else:
                return f"[GENERALIZED:{category}]"
                
        elif rule == "date_shift":
            return shift_date(text, self.date_shift_days)
            
        # Default fallback
        return f"[REDACTED:{category}]"


