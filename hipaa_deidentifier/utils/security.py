"""
Security Utilities

Provides security functions for hashing and anonymizing PHI.
"""
import os
import hmac
import hashlib


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


def get_salt_from_config(config: dict) -> str:
    """
    Retrieves the salt value from configuration.
    
    Args:
        config: The configuration dictionary
        
    Returns:
        The salt value as a string
    """
    return config.get("security", {}).get("salt", "DEFAULT_SALT_CHANGE_IN_PRODUCTION")


