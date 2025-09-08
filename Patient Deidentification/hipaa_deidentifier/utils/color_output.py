"""
Color Output Utilities for PHI De-identification

Provides simple color coding for different PHI categories to make de-identification
results more visually interpretable.
"""

# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

# Simple color mapping for PHI categories
PHI_CATEGORY_COLORS = {
    'NAME': Colors.RED,
    'PERSON': Colors.RED,
    'DATE': Colors.YELLOW,
    'GEOGRAPHIC_SUBDIVISION': Colors.GREEN,
    'LOCATION': Colors.GREEN,
    'PHONE_NUMBER': Colors.BLUE,
    'FAX_NUMBER': Colors.BLUE,
    'EMAIL_ADDRESS': Colors.MAGENTA,
    'US_SSN': Colors.CYAN,
    'SSN': Colors.CYAN,
    'MRN': Colors.WHITE,
    'HEALTH_PLAN_ID': Colors.RED,
    'ACCOUNT_NUMBER': Colors.GREEN,
    'LICENSE_NUMBER': Colors.YELLOW,
    'VEHICLE_ID': Colors.BLUE,
    'MEDICAL_DEVICE_ID': Colors.MAGENTA,
    'URL': Colors.CYAN,
    'IP_ADDRESS': Colors.WHITE,
    'BIOMETRIC_ID': Colors.YELLOW,
    'PHOTO_ID': Colors.YELLOW,
    # OTHER_ID removed as per user request
    'ENCOUNTER_ID': Colors.RED,
    'ORGANIZATION': Colors.GREEN,
}

def colorize_text(text: str, category: str) -> str:
    """
    Colorize text based on PHI category.
    
    Args:
        text: The text to colorize
        category: The PHI category
        
    Returns:
        Colorized text string
    """
    color = PHI_CATEGORY_COLORS.get(category, Colors.WHITE)
    return f"{color}{text}{Colors.RESET}"

def colorize_deidentified_text(text: str, entities: list) -> str:
    """
    Colorize de-identified text by adding color to redacted portions based on category.
    
    Args:
        text: The de-identified text
        entities: List of PHI entities with start/end positions and categories
        
    Returns:
        Colorized de-identified text
    """
    # Sort entities by position
    # Handle both dictionary format and PHIEntity objects
    try:
        # Try PHIEntity objects first
        sorted_entities = sorted(entities, key=lambda e: e.start)
    except (AttributeError, TypeError):
        # Fall back to dictionary format
        sorted_entities = sorted(entities, key=lambda e: e['start'])
    
    # Find all [REDACTED:CATEGORY] or PATIENT_xxx patterns in the text
    import re
    redacted_pattern = r'\[REDACTED:([A-Z_]+)\]|PATIENT_[a-f0-9]+'
    
    # Special handling for email addresses - fix split emails
    email_pattern = r'([a-zA-Z0-9_.+-]+)@\[REDACTED:URL\]'
    for match in re.finditer(email_pattern, text):
        full_match = match.group(0)
        # Replace with [REDACTED:EMAIL_ADDRESS]
        text = text.replace(full_match, '[REDACTED:EMAIL_ADDRESS]')
    
    # Build the colorized text
    result = text
    for match in re.finditer(redacted_pattern, text):
        redacted_text = match.group(0)
        # Get category from [REDACTED:CATEGORY] format
        if redacted_text.startswith('[REDACTED:'):
            category = redacted_text[10:-1]  # Extract category from [REDACTED:CATEGORY]
        else:
            category = 'NAME'  # For PATIENT_xxx patterns
            
        # Replace with colorized version
        colored_text = colorize_text(redacted_text, category)
        result = result.replace(redacted_text, colored_text, 1)
    
    return result