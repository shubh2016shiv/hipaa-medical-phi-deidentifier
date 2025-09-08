"""
Security Utilities

Provides security functions for hashing and anonymizing PHI.
"""
import os
import hmac
import hashlib
import re
from typing import Dict, Optional


def generate_secure_hash(text: str, salt: str, length: int = 12) -> str:
    """
    Generates a secure hash for the given text using HMAC-SHA256.
    
    Args:
        text: The text to hash
        salt: A salt value to make the hash more secure
        length: The desired length of the output hash code (minimum 8 recommended)
        
    Returns:
        A hexadecimal string of the specified length
    """
    # Validate inputs
    if not text:
        raise ValueError("Cannot hash empty text")
        
    if not salt or salt == "DEFAULT_SALT_REPLACE_IN_PRODUCTION":
        # Use a fallback salt if none provided, but this is not recommended for production
        import warnings
        warnings.warn("Using default salt for hashing. This is not secure for production use.")
        salt = "HIPAA_DEFAULT_SALT_NOT_FOR_PRODUCTION_USE"
    
    # Enforce minimum length for security
    actual_length = max(length, 8)
        
    # Generate hash using HMAC-SHA256
    h = hmac.new(salt.encode('utf-8'), text.encode('utf-8'), hashlib.sha256)
    return h.hexdigest()[:actual_length]


def get_salt_from_config(config: Optional[dict] = None) -> str:
    """
    Retrieves the salt value from centralized configuration.

    Args:
        config: Optional configuration dictionary (deprecated - uses centralized config)

    Returns:
        The salt value as a string
    """
    # Use centralized configuration system
    from config.config import config as global_config
    return global_config.get_salt()


def normalize_name(name: str) -> str:
    """
    Normalize a name for consistent pseudonym generation.
    
    This helps ensure that "John Smith", "JOHN SMITH", and "Smith, John" 
    all map to the same pseudonym.
    
    Args:
        name: The name to normalize
        
    Returns:
        Normalized name string
    """
    if not name:
        return ""
        
    # Convert to lowercase
    normalized = name.lower()
    
    # Remove punctuation and extra whitespace
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Handle "Last, First" format
    if ',' in name:
        parts = name.split(',', 1)
        if len(parts) == 2:
            last = parts[0].strip()
            first = parts[1].strip()
            normalized = f"{first} {last}"
    
    # Sort name parts for consistency
    parts = normalized.split()
    if len(parts) > 1:
        # If more than 2 parts, assume first and last are most important
        if len(parts) > 2:
            parts = [parts[0], parts[-1]]
        parts.sort()
        normalized = " ".join(parts)
    
    return normalized


class PseudonymManager:
    """
    Manages consistent pseudonym generation for PHI entities.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize the pseudonym manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.salt = get_salt_from_config(config)
        self.pseudonym_cache = {}  # Cache of entity text to pseudonym mapping
        
    def get_pseudonym(self, entity_text: str, entity_type: str, patient_id: Optional[str] = None) -> str:
        """
        Get a consistent pseudonym for an entity.
        
        Args:
            entity_text: The original entity text
            entity_type: The type of entity (e.g., NAME, MRN)
            patient_id: Optional patient identifier for context
            
        Returns:
            A consistent pseudonym for the entity
        """
        # Fix issue #4: Hashes / Noise Injected
        # Don't generate pseudonyms for very short text (likely false positives)
        if len(entity_text.strip()) < 3 and entity_type not in ["AGE", "AGE_OVER_89"]:
            return entity_text
            
        # Create a cache key that includes entity type
        if entity_type == "NAME":
            # For names, normalize to ensure consistency
            normalized_text = normalize_name(entity_text)
            cache_key = f"{entity_type}:{normalized_text}"
        else:
            cache_key = f"{entity_type}:{entity_text}"
            
        # Add patient context if available
        if patient_id:
            cache_key = f"{patient_id}:{cache_key}"
            
        # Use cached value if available
        if cache_key in self.pseudonym_cache:
            return self.pseudonym_cache[cache_key]
            
        # Generate a hash code
        hash_code = generate_secure_hash(cache_key, self.salt)
        
        # Format according to configuration
        format_template = (
            self.config.get("pseudonym_formats", {}).get(entity_type) or 
            self.config.get("pseudonym_formats", {}).get("DEFAULT") or 
            "{code}"
        )
        pseudonym = format_template.format(code=hash_code)
        
        # Cache the result
        self.pseudonym_cache[cache_key] = pseudonym
        
        return pseudonym