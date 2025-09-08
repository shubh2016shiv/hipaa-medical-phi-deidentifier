"""
PHI Entity Model

Defines the data structures for representing detected PHI entities.
"""
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple
import re

from .phi_taxonomy import (
    normalize_category, 
    is_atomic_entity, 
    get_entity_priority,
    is_whitelisted_header
)


@dataclass
class PHIEntity:
    """
    Represents a detected Protected Health Information (PHI) entity in text.
    
    Attributes:
        start: Start position of the entity in the text
        end: End position of the entity in the text
        category: Category of PHI (e.g., NAME, MRN, SSN)
        confidence: Confidence score of the detection (0.0 to 1.0)
        text: The actual text content of the entity
    """
    start: int
    end: int
    category: str
    confidence: float
    text: str

    def __post_init__(self):
        """Normalize the category after initialization."""
        self.category = normalize_category(self.category)


def _find_full_atomic_entity(text: str, start_pos: int, end_pos: int, category: str) -> Tuple[int, int]:
    """
    Find the full boundaries of an atomic entity in the text.
    
    Args:
        text: The original text
        start_pos: Start position of the detected entity
        end_pos: End position of the detected entity
        category: Category of the entity
        
    Returns:
        Tuple of (start, end) positions for the full atomic entity
    """
    # Define patterns for different atomic entity types
    patterns = {
        "URL": r'https?://[^\s<>"]+(?:/[^\s<>"]*)?(?:[?&][^\s<>"]*)*',
        "EMAIL_ADDRESS": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        "IP_ADDRESS": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        "SSN": r'\b(?!\d{5}-\d{4})\d{3}[- ]?\d{2}[- ]?\d{4}\b(?!\s*[A-Z]{2})',
        "VEHICLE_ID": r'\b[A-Z0-9]{17}\b|\bVIN[-: ]?[A-Z0-9]+',
        "ACCOUNT_NUMBER": r'\bACC[-: ]?[A-Z0-9]+',
        "HEALTH_PLAN_ID": r'\b[A-Z]{2,5}[-: ]?\d+',
        "MRN": r'\bMRN[-: ]?[A-Z0-9]+|\b\d{6,10}\b',
        # Add comprehensive date patterns to properly capture full dates
        "DATE": r'\b(?:\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}|\d{4}[-/\.]\d{1,2}[-/\.]\d{1,2}|\d{1,2}[-/\s][A-Za-z]{3,9}[-/\s]\d{2,4}|[A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?[,\s]+\d{2,4})\b',
    }
    
    # Get the pattern for this entity type
    pattern = patterns.get(category)
    if not pattern:
        return start_pos, end_pos
    
    # Look for the full token around the entity
    # Search in a window around the entity
    window_start = max(0, start_pos - 50)
    window_end = min(len(text), end_pos + 50)
    window_text = text[window_start:window_end]
    
    # Adjust the match positions to account for the window
    entity_rel_start = start_pos - window_start
    entity_rel_end = end_pos - window_start
    
    # Find all matches in the window
    matches = list(re.finditer(pattern, window_text))
    
    # Find the match that contains our entity
    for match in matches:
        # Check if the match overlaps with our entity
        if (match.start() <= entity_rel_start and match.end() >= entity_rel_end) or \
           (match.start() >= entity_rel_start and match.start() < entity_rel_end) or \
           (match.end() > entity_rel_start and match.end() <= entity_rel_end):
            # Found a match that overlaps with our entity
            return window_start + match.start(), window_start + match.end()
    
    # Special case for URLs, email addresses, and dates - try more aggressive patterns
    if category == "URL":
        # Look for full URLs including domain, path, and query parameters
        url_patterns = [
            r'https?://[^\s<>"]+(?:/[^\s<>"]*)?(?:[?&][^\s<>"]*)*',  # Full URLs with query params
            r'(?:https?://)?(?:www\.)?[a-zA-Z0-9][-a-zA-Z0-9]*(?:\.[a-zA-Z0-9][-a-zA-Z0-9]*)+(?:/[^\s<>"]*)?',  # Basic URLs
        ]
        
        for url_pattern in url_patterns:
            matches = list(re.finditer(url_pattern, window_text))
            for match in matches:
                if (match.start() <= entity_rel_start and match.end() >= entity_rel_end) or \
                   (match.start() >= entity_rel_start and match.start() < entity_rel_end) or \
                   (match.end() > entity_rel_start and match.end() <= entity_rel_end):
                    return window_start + match.start(), window_start + match.end()
    
    elif category == "EMAIL_ADDRESS":
        # Try to find the full email address
        email_parts = window_text[entity_rel_start:entity_rel_end].split('@')
        if len(email_parts) == 2:
            # Look for the full email pattern
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            matches = list(re.finditer(email_pattern, window_text))
            for match in matches:
                if '@' in window_text[match.start():match.end()]:
                    return window_start + match.start(), window_start + match.end()
                    
    elif category == "DATE":
        # Enhanced date pattern matching to capture full dates
        # This handles common formats like MM/DD/YYYY, YYYY-MM-DD, Month DD, YYYY, etc.
        date_patterns = [
            # Numeric date formats - more comprehensive patterns
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
        
        # Try each date pattern
        for date_pattern in date_patterns:
            matches = list(re.finditer(date_pattern, window_text, re.IGNORECASE))
            for match in matches:
                if (match.start() <= entity_rel_start and match.end() >= entity_rel_end) or \
                   (match.start() >= entity_rel_start and match.start() < entity_rel_end) or \
                   (match.end() > entity_rel_start and match.end() <= entity_rel_end):
                    return window_start + match.start(), window_start + match.end()
    
    # No better match found, return the original boundaries
    return start_pos, end_pos


def _expand_atomic_entities(entities: List[PHIEntity], text: str) -> List[PHIEntity]:
    """
    Expand atomic entities to include the full token they're part of.
    
    Args:
        entities: List of detected PHI entities
        text: The original text
        
    Returns:
        List of PHI entities with atomic entities expanded to full tokens
    """
    expanded = []
    
    for entity in entities:
        # Skip if not an atomic entity type
        if not is_atomic_entity(entity.category):
            expanded.append(entity)
            continue
        
        # Find the full atomic entity
        start, end = _find_full_atomic_entity(text, entity.start, entity.end, entity.category)
        
        # Create a new entity with the expanded boundaries
        if start != entity.start or end != entity.end:
            expanded.append(PHIEntity(
                start=start,
                end=end,
                category=entity.category,
                confidence=entity.confidence,
                text=text[start:end]
            ))
        else:
            expanded.append(entity)
    
    return expanded


def _is_medication(text: str) -> bool:
    """
    Check if text is a common medication name.
    
    Args:
        text: Text to check
        
    Returns:
        True if text is a medication name
    """
    # Common medication names that should not be redacted
    medications = {
        'metformin', 'lisinopril', 'atorvastatin', 'aspirin', 'clopidogrel',
        'metoprolol', 'amlodipine', 'hydrochlorothiazide', 'simvastatin',
        'pravastatin', 'rosuvastatin', 'losartan', 'valsartan', 'candesartan',
        'irbesartan', 'olmesartan', 'telmisartan', 'azilsartan', 'eprosartan',
        'carvedilol', 'propranolol', 'atenolol', 'nebivolol', 'bisoprolol',
        'labetalol', 'acebutolol', 'betaxolol', 'carteolol', 'esmolol',
        'penbutolol', 'pindolol', 'sotalol', 'timolol', 'furosemide',
        'hydrochlorothiazide', 'spironolactone', 'eplerenone', 'triamterene',
        'amiloride', 'bumetanide', 'torsemide', 'indapamide', 'chlorthalidone',
        'warfarin', 'rivaroxaban', 'apixaban', 'edoxaban', 'dabigatran',
        'heparin', 'enoxaparin', 'dalteparin', 'fondaparinux', 'argatroban',
        'bivalirudin', 'lepirudin', 'desirudin', 'insulin', 'glipizide',
        'glyburide', 'glimepiride', 'repaglinide', 'nateglinide', 'pioglitazone',
        'rosiglitazone', 'sitagliptin', 'saxagliptin', 'linagliptin', 'alogliptin',
        'vildagliptin', 'exenatide', 'liraglutide', 'dulaglutide', 'semaglutide',
        'albiglutide', 'lixisenatide', 'canagliflozin', 'dapagliflozin', 'empagliflozin',
        'ertugliflozin', 'bexagliflozin', 'sotagliflozin', 'acarbose', 'miglitol',
        'bromocriptine', 'colesevelam', 'metformin', 'phenformin', 'buformin',
        'miglitol', 'acarbose', 'voglibose', 'miglitol', 'acarbose'
    }
    
    return text.lower().strip() in medications


def _filter_whitelisted_headers(entities: List[PHIEntity], text: str) -> List[PHIEntity]:
    """
    Filter out entities that match whitelisted header terms or medications.
    
    Args:
        entities: List of detected PHI entities
        text: The original text
        
    Returns:
        Filtered list of PHI entities
    """
    filtered = []
    
    for entity in entities:
        entity_text = text[entity.start:entity.end]
        
        # Skip if it's a whitelisted header term
        if is_whitelisted_header(entity_text):
            continue
            
        # Skip if it's a medication name
        if _is_medication(entity_text):
            continue
            
        # Skip if it's a clinical measurement (vitals/labs)
        if _is_clinical_measurement(entity_text):
            continue
            
        filtered.append(entity)
    
    return filtered


def _is_clinical_measurement(text: str) -> bool:
    """
    Check if text represents a clinical measurement that should not be redacted.
    
    Args:
        text: Text to check
        
    Returns:
        True if the text is a clinical measurement
    """
    # Vital sign patterns - enhanced to catch more medical measurements
    vital_patterns = [
        r"\bBP\s+\d{2,3}/\d{2,3}\b",  # Blood pressure
        r"\bHR\s+\d{2,3}\b",           # Heart rate
        r"\bRR\s+\d{1,2}\b",           # Respiratory rate
        r"\bT\s+\d{2}\.\d\b",          # Temperature
        r"\bTemp\s+\d{2}\.\d\b",       # Temperature
        r"\bO2\s+\d{1,3}%\b",          # Oxygen saturation
        r"\bSPO2\s+\d{1,3}%\b",        # Oxygen saturation
        r"\bWT\s+\d{1,3}\.\d\b",       # Weight
        r"\bHT\s+\d{1,3}\b",           # Height
        r"\bBMI\s+\d{1,2}\.\d\b",      # BMI
        # Additional vital sign patterns
        r"\b\d{2,3}/\d{2,3}\s*mmHg\b",  # Blood pressure with units
        r"\b\d{2,3}\s*bpm\b",           # Heart rate with units
        r"\b\d{2}\.\d\s*F\b",           # Temperature with units
        r"\b\d{1,3}\.\d\s*kg/m\^2\b",   # BMI with units
        r"\b\d{1,3}\s*mg/dL\b",         # Blood glucose
        r"\b\d{1,2}\.\d\s*mg/dL\b",     # Creatinine
    ]
    
    # Lab value patterns - enhanced to catch more lab measurements
    lab_patterns = [
        r"\bA1c\s+\d{1,2}\.\d%\b",     # Hemoglobin A1c
        r"\bHbA1c\s+\d{1,2}\.\d%\b",   # Hemoglobin A1c
        r"\bLDL\s+\d{1,3}\b",          # LDL cholesterol
        r"\bHDL\s+\d{1,3}\b",          # HDL cholesterol
        r"\bTSH\s+\d{1,2}\.\d{1,3}\b", # Thyroid stimulating hormone
        r"\bWBC\s+\d{1,2}\.\d\b",      # White blood cell count
        r"\bHGB\s+\d{1,2}\.\d\b",      # Hemoglobin
        r"\bHCT\s+\d{1,2}\.\d\b",      # Hematocrit
        r"\bPLT\s+\d{1,3}\b",          # Platelet count
        r"\bCR\s+\d{1,2}\.\d{1,2}\b",  # Creatinine
        r"\bBUN\s+\d{1,2}\b",          # Blood urea nitrogen
        r"\bNA\s+\d{3}\b",             # Sodium
        r"\bK\s+\d{1,2}\.\d\b",        # Potassium
        r"\bGLU\s+\d{1,3}\b",          # Glucose
        # Additional lab patterns with units
        r"\b\d{1,2}\.\d%\b",           # Percentage values (A1c, etc.)
        r"\b\d{1,3}\s*mg/dL\b",        # Lab values with units
        r"\b\d{1,2}\.\d\s*mg/dL\b",    # Lab values with decimal units
        r"\b\d{1,3}\s*mg\b",           # Medication doses
        r"\b\d{1,2}\.\d\s*mg\b",       # Medication doses with decimals
    ]
    
    # Check if text matches any of the patterns
    for pattern in vital_patterns + lab_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False


def _resolve_overlaps(entities: List[PHIEntity]) -> List[PHIEntity]:
    """
    Resolve overlapping entities with a more robust, multi-pass strategy.
    
    This function handles overlaps by prioritizing specific, high-confidence entities
    and ensuring that shorter, less-specific entities contained within longer ones
    are correctly discarded.
    """
    if not entities:
        return []

    # First pass: High-confidence filtering and length-based sorting
    # Prioritize longer entities to handle cases where a shorter entity is a subset of a longer one.
    # E.g., "03/12/1958" (UNKNOWN) vs. "DOB: 03/12/1958" (DATE)
    sorted_entities = sorted(entities, key=lambda e: (e.start, -(e.end - e.start), get_entity_priority(e.category), -e.confidence))

    # Second pass: Iterative removal of overlapping sub-entities
    # This loop ensures that once a primary entity is chosen, any other entities that are fully
    # contained within it are removed.
    resolved = []
    for current_entity in sorted_entities:
        is_sub_entity = False
        for existing_entity in resolved:
            # Check if the current entity is fully contained within an existing one
            if current_entity.start >= existing_entity.start and current_entity.end <= existing_entity.end:
                # Rule: If a high-priority entity contains a lower-priority one, keep the high-priority one.
                # This handles cases like a DATE containing a mis-categorized UNKNOWN.
                current_priority = get_entity_priority(current_entity.category)
                existing_priority = get_entity_priority(existing_entity.category)
                
                if current_priority > existing_priority: # Higher number means lower priority
                     is_sub_entity = True
                     break
        
        if not is_sub_entity:
            resolved.append(current_entity)

    # Third pass: Final check to remove any remaining overlaps and handle special cases
    final_result = []
    for current_entity in resolved:
        has_overlap = False
        # Special case for dates inside filenames or URLs
        if current_entity.category in ["URL", "PHOTO_ID"] and any(char.isdigit() for char in current_entity.text):
            date_in_text = re.search(r'\d{4}[-/_]\d{1,2}[-/_]\d{1,2}', current_entity.text)
            if date_in_text:
                # If a date is found, we should prioritize the date entity if one exists for that span
                date_start = current_entity.start + date_in_text.start()
                date_end = current_entity.start + date_in_text.end()
                
                # Check if a high-confidence date entity exists for this exact span
                found_date_entity = False
                for e in sorted_entities:
                    if e.category == "DATE" and e.start == date_start and e.end == date_end and e.confidence > 0.8:
                        if e not in final_result:
                             final_result.append(e)
                        found_date_entity = True
                        break
                if found_date_entity:
                    continue # Skip adding the URL/PHOTO_ID if we added the date

        for final_entity in final_result:
            if max(current_entity.start, final_entity.start) < min(current_entity.end, final_entity.end):
                # Overlap detected. Decide which one to keep based on our robust criteria.
                current_priority = get_entity_priority(current_entity.category)
                final_priority = get_entity_priority(final_entity.category)
                
                # Prioritize based on category, then confidence, then length.
                if current_priority < final_priority:
                    final_result.remove(final_entity)
                    final_result.append(current_entity)
                elif final_priority < current_priority:
                    pass # Keep the existing final_entity
                else: # Same priority, check confidence
                    if current_entity.confidence > final_entity.confidence:
                        final_result.remove(final_entity)
                        final_result.append(current_entity)
                has_overlap = True
                break
        
        if not has_overlap:
            final_result.append(current_entity)
            
    return final_result


def merge_overlapping_entities(rule_entities: List[PHIEntity], ml_entities: List[PHIEntity], text: str) -> List[PHIEntity]:
    """
    Merges potentially overlapping PHI entities from different detection methods.
    
    When entities overlap:
    1. Expand atomic entities to include full tokens
    2. Filter out whitelisted header terms
    3. Normalize all entity categories
    4. Resolve overlaps based on entity priority
    
    Args:
        rule_entities: Entities detected by rule-based methods
        ml_entities: Entities detected by machine learning methods
        text: The original text
        
    Returns:
        A list of merged PHI entities with resolved overlaps
    """
    # Combine all entities
    all_entities = rule_entities + ml_entities
    
    # No entities to merge
    if not all_entities:
        return []
        
    # 1. Expand atomic entities to include full tokens
    expanded_entities = _expand_atomic_entities(all_entities, text)
    
    # 2. Filter out whitelisted header terms
    filtered_entities = _filter_whitelisted_headers(expanded_entities, text)
    
    # 3. Normalize all entity categories (done in PHIEntity.__post_init__)
    
    # 4. Resolve overlaps based on entity priority
    resolved_entities = _resolve_overlaps(filtered_entities)
    
    # Make sure all entities have text populated
    for i, entity in enumerate(resolved_entities):
        if not entity.text:
            resolved_entities[i] = PHIEntity(
                start=entity.start,
                end=entity.end,
                category=entity.category,
                confidence=entity.confidence,
                text=text[entity.start:entity.end]
            )
            
    return resolved_entities