"""
PHI Taxonomy and Entity Definitions

Defines standardized HIPAA taxonomy, atomic entity types, and entity precedence rules.
"""

# Standardized HIPAA taxonomy mapping
# Maps various entity labels to a consistent set of HIPAA-compliant categories
HIPAA_LABELS = {
    # Person names
    "PERSON": "NAME",
    "NAME": "NAME",
    
    # Dates
    "DATE": "DATE",
    
    # Geographic subdivisions
    "ADDRESS": "LOCATION",
    "LOCATION": "LOCATION",
    "CITY": "LOCATION",
    "STATE": "LOCATION",
    "ZIP": "LOCATION",
    "GEOGRAPHIC_SUBDIVISION": "LOCATION",
    
    # Contact information
    "EMAIL_ADDRESS": "EMAIL_ADDRESS",
    "PHONE_NUMBER": "PHONE_NUMBER",
    "FAX_NUMBER": "FAX_NUMBER",
    
    # Identifiers
    "US_SSN": "US_SSN",
    "SSN": "US_SSN",
    "MEDICAL_RECORD_NUMBER": "MRN",
    "MRN": "MRN",
    "ENCOUNTER_ID": "ENCOUNTER_ID",
    "ACCOUNT_NUMBER": "ACCOUNT_NUMBER",
    "HEALTH_PLAN_BENEFICIARY_NUMBER": "HEALTH_PLAN_ID",
    "HEALTH_PLAN_ID": "HEALTH_PLAN_ID",
    "LICENSE_NUMBER": "LICENSE_NUMBER",
    "VEHICLE_ID": "VEHICLE_ID",
    "VIN": "VEHICLE_ID",
    "DEVICE_ID": "DEVICE_ID",
    
    # Web identifiers
    "URL": "URL",
    "IP_ADDRESS": "IP_ADDRESS",
    
    # Biometric and photo identifiers
    "BIOMETRIC_ID": "BIOMETRIC_ID",
    "FULL_FACE_PHOTO": "PHOTO_ID",
    "PHOTO_ID": "PHOTO_ID",
    
    # Age information
    "AGE_OVER_89": "AGE_OVER_89",
    
    # Other categories
    "OTHER_ID": "OTHER_ID",
    "ORGANIZATION": "ORGANIZATION",
    
    # Remap problematic categories
    "IN_PAN": "OTHER_ID",      # India PAN number should be mapped to OTHER_ID
}

# Atomic entity types - these should never be partially replaced
# They should be treated as a single indivisible token
ATOMIC_ENTITIES = {
    "URL", 
    "EMAIL_ADDRESS", 
    "IP_ADDRESS", 
    "SSN",
    "VEHICLE_ID", 
    "DEVICE_ID", 
    "ACCOUNT_NUMBER",
    "HEALTH_PLAN_ID", 
    "LICENSE_NUMBER", 
    "MRN", 
    "ENCOUNTER_ID",
    "DATE"  # Add DATE as an atomic entity to ensure complete date redaction
}

# Entity precedence for overlap resolution
# Highest precedence (most specific) first
ENTITY_PRECEDENCE = [
    "URL",
    "EMAIL_ADDRESS",
    "IP_ADDRESS",
    "SSN",
    "VEHICLE_ID",
    "DEVICE_ID",
    "HEALTH_PLAN_ID",
    "ACCOUNT_NUMBER",
    "LICENSE_NUMBER",
    "MRN",
    "ENCOUNTER_ID",
    "PHONE_NUMBER",
    "FAX_NUMBER",
    "DATE",
    "PHOTO_ID",
    "BIOMETRIC_ID",
    "NAME",
    "GEOGRAPHIC_SUBDIVISION",
    "AGE_OVER_89",
    "OTHER_ID",
    "ORGANIZATION"  # Moved to lowest priority to prevent false positives
]

# Convert precedence list to a dict for O(1) lookup
ENTITY_PRIORITY = {label: i for i, label in enumerate(ENTITY_PRECEDENCE)}

# Header/boilerplate terms to ignore - simplified to essentials
HEADER_WHITELIST = {
    # Document headers
    "HIPAA",
    "Safe Harbor",
    "Identifiers",
    "Test",
    "Example",
    
    # Common section headers in clinical notes
    "Chief Complaint",
    "History of Present Illness",
    "HPI",
    "Past Medical History",
    "PMH",
    "Medications",
    "Assessment",
    "Plan",
    "Follow-up",
    "Labs",
    "Vitals",
    "Discharge Meds",
    "Hospital Course",
    "Principal Diagnosis",
    "Procedure",
    
    # Common numbers that shouldn't be redacted
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "50", "75", "80", "81", "100", "150", "200", "250", "500", "1000",
    
    # Medical terms that shouldn't be redacted
    "NSTEMI",
    "STEMI",
    "CABG",
    "T1DM",
    "T2DM",
    "HTN",
    "POD",
    "PO",
    "IV",
    "BID",
    "TID",
    "QID",
    "mg",
    "mcg",
    "kg",
    "mmHg",
    "BP",
    "HR",
    "Temp",
    "A1c",
    "LDL",
    "HDL",
    "triple-vessel disease",
    "post-op",
    "pleural effusion",
    "succinate",
    "daily",
    "nightly",
    "weekly",
    # Additional medical terms
    "SGLT2",
    "GLP-1",
    "RA",
    "BMP",
    "DASH",
    "CGM",
    "DexPro",
    "bpm",
    "F",
    "kg/m^2",
    "mg/dL",
    "brisk walking",
    "fasting glucose",
    "post-prandial",
    "morning dizziness",
    "vision changes",
    "CP/SOB",
    "retinal exam",
    "basal",
    "hypoglycemia",
    "hyperlipidemia",
    "suboptimal control",
    
    # Common medications
    "metformin",
    "lisinopril",
    "atorvastatin",
    "aspirin",
    "clopidogrel",
    "metoprolol",
    "insulin",
}

def normalize_category(category: str) -> str:
    """
    Normalize an entity category to the standardized HIPAA taxonomy.
    
    Args:
        category: The original category name
        
    Returns:
        The normalized category name according to HIPAA taxonomy
    """
    return HIPAA_LABELS.get(category, "UNKNOWN")

def is_atomic_entity(category: str) -> bool:
    """
    Check if an entity category is considered atomic (should not be partially replaced).
    
    Args:
        category: The entity category
        
    Returns:
        True if the entity is atomic, False otherwise
    """
    return category in ATOMIC_ENTITIES

def get_entity_priority(category: str) -> int:
    """
    Get the priority of an entity category for overlap resolution.
    Lower number = higher priority.
    
    Args:
        category: The entity category
        
    Returns:
        The priority value (lower is higher priority)
    """
    return ENTITY_PRIORITY.get(category, len(ENTITY_PRECEDENCE))  # Default to lowest priority

def is_whitelisted_header(text: str) -> bool:
    """
    Check if text contains whitelisted header terms that should be ignored.
    
    Args:
        text: The text to check
        
    Returns:
        True if the text contains whitelisted header terms
    """
    return text in HEADER_WHITELIST