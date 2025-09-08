"""
Clinical Pattern Detection

Specialized detection patterns for clinical notes, including:
- Section headers (Patient Name, MRN, DOB)
- Initials and nicknames
- Hospital and clinic names
- Relatives and contacts
- Special handling for ages ≥ 89
- Numeric guards for labs and vitals
- Catch-all for long numeric identifiers
"""
import re
from typing import List, Dict, Tuple, Set, Optional

from ..models.phi_entity import PHIEntity


def detect_section_headers(text: str) -> List[PHIEntity]:
    """
    Detect PHI in common clinical note section headers.
    
    Looks for patterns like "Patient Name: John Smith", "MRN: 123456789", etc.
    
    Args:
        text: The clinical note text
        
    Returns:
        List of detected PHI entities
    """
    entities = []
    
    # Process the text line by line
    for line_match in re.finditer(r"([^\n]+)", text):
        line = line_match.group(1)
        line_start = line_match.start()
        
        # Patient name patterns
        name_match = re.search(r"(?:patient\s+name|name|patient)\s*:\s*([^\n]+)", line, re.IGNORECASE)
        if name_match:
            value = name_match.group(1).strip()
            if value and len(value) > 1:  # Avoid empty or single-character matches
                start = line_start + name_match.start(1)
                end = line_start + name_match.end(1)
                entities.append(PHIEntity(
                    start=start,
                    end=end,
                    category="NAME",
                    confidence=0.95,
                    text=value
                ))
        
        # MRN patterns
        mrn_match = re.search(r"(?:mrn|medical\s+record\s+number|record\s+number)\s*:\s*([^\n]+)", line, re.IGNORECASE)
        if mrn_match:
            value = mrn_match.group(1).strip()
            if value and len(value) > 1:
                start = line_start + mrn_match.start(1)
                end = line_start + mrn_match.end(1)
                entities.append(PHIEntity(
                    start=start,
                    end=end,
                    category="MRN",
                    confidence=0.95,
                    text=value
                ))
        
        # DOB patterns
        dob_match = re.search(r"(?:dob|date\s+of\s+birth|birth\s+date)\s*:\s*([^\n]+)", line, re.IGNORECASE)
        if dob_match:
            value = dob_match.group(1).strip()
            if value and len(value) > 1:
                start = line_start + dob_match.start(1)
                end = line_start + dob_match.end(1)
                entities.append(PHIEntity(
                    start=start,
                    end=end,
                    category="DATE",
                    confidence=0.95,
                    text=value
                ))
                
        # Age patterns with special handling for ages ≥ 89
        age_match = re.search(r"(?:age|patient\s+age)\s*:\s*(\d{1,3})", line, re.IGNORECASE)
        if age_match:
            age_value = age_match.group(1).strip()
            if age_value:
                age = int(age_value)
                start = line_start + age_match.start(1)
                end = line_start + age_match.end(1)
                if age >= 90:
                    entities.append(PHIEntity(
                        start=start,
                        end=end,
                        category="AGE_OVER_89",
                        confidence=1.0,
                        text=age_value
                    ))
    
    return entities


def detect_initials_and_nicknames(text: str) -> List[PHIEntity]:
    """
    Detect initials and nicknames in clinical notes.
    
    Looks for patterns like "J.S.", "J. S.", or "Johnny (nickname John)"
    
    Args:
        text: The clinical note text
        
    Returns:
        List of detected PHI entities
    """
    entities = []
    
    # Detect initials like "J.S." or "J. S."
    initial_pattern = r"\b[A-Z]\.\s*[A-Z]\.?\b"
    for match in re.finditer(initial_pattern, text):
        entities.append(PHIEntity(
            start=match.start(),
            end=match.end(),
            category="NAME",
            confidence=0.9,
            text=match.group()
        ))
    
    # Detect nicknames like "Johnny (nickname John)" or "Johnny (aka John)"
    nickname_pattern = r"\b[A-Z][a-z]+\s+\((?:nickname|aka|AKA|a\.k\.a\.|called)\s+[A-Z][a-z]+\)"
    for match in re.finditer(nickname_pattern, text):
        entities.append(PHIEntity(
            start=match.start(),
            end=match.end(),
            category="NAME",
            confidence=0.9,
            text=match.group()
        ))
        
    # Detect parenthetical names like "John (Smith)"
    parenthetical_name = r"\b[A-Z][a-z]+\s+\([A-Z][a-z]+\)"
    for match in re.finditer(parenthetical_name, text):
        entities.append(PHIEntity(
            start=match.start(),
            end=match.end(),
            category="NAME",
            confidence=0.85,
            text=match.group()
        ))
    
    return entities


def detect_facility_names(text: str) -> List[PHIEntity]:
    """
    Detect hospital and clinic names in clinical notes.
    
    Args:
        text: The clinical note text
        
    Returns:
        List of detected PHI entities
    """
    entities = []
    
    # More specific facility patterns to avoid over-detection
    facility_patterns = [
        # Full hospital names with specific patterns
        r"\b[A-Z][a-z]+\s+(?:Hospital|Medical Center|Health System|Healthcare)\b",
        r"\b[A-Z][a-z]+\s+(?:Memorial|Regional|Community)\s+(?:Hospital|Medical Center)\b",
        r"\b[A-Z][a-z]+\s+University\s+(?:Hospital|Medical Center|Health System)\b",
        r"\b[A-Z][a-z]+\s+(?:Center|Institute)\s+for\s+[A-Z][a-z]+\b",
        # Clinic patterns
        r"\b[A-Z][a-z]+\s+(?:Clinic|Medical Group|Physicians)\b",
    ]
    
    # Process the text line by line
    for line_match in re.finditer(r"([^\n]+)", text):
        line = line_match.group(1)
        line_start = line_match.start()
        
        # Check each facility pattern
        for pattern in facility_patterns:
            facility_match = re.search(pattern, line, re.IGNORECASE)
            if facility_match:
                facility_text = facility_match.group().strip()
                # Additional validation: make sure it's a proper facility name
                if len(facility_text.split()) >= 2:  # At least 2 words
                    start = line_start + facility_match.start()
                    end = line_start + facility_match.end()
                    entities.append(PHIEntity(
                        start=start,
                        end=end,
                        category="ORGANIZATION",
                        confidence=0.85,
                        text=facility_text
                    ))
                    break  # Only one facility per line
    
    return entities


def detect_relatives_and_contacts(text: str) -> List[PHIEntity]:
    """
    Detect mentions of relatives and contacts in clinical notes.
    
    Looks for patterns like "wife Mary", "son John", etc.
    
    Args:
        text: The clinical note text
        
    Returns:
        List of detected PHI entities
    """
    entities = []
    
    # List of relationship terms
    relationships = [
        "wife", "husband", "spouse", "partner", 
        "son", "daughter", "child", "children",
        "mother", "father", "parent", "guardian",
        "sister", "brother", "sibling",
        "aunt", "uncle", "cousin",
        "grandmother", "grandfather", "grandparent",
        "grandson", "granddaughter", "grandchild"
    ]
    
    # Create pattern to match relationship followed by capitalized name
    pattern = r"\b(" + "|".join(relationships) + r")\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    
    for match in re.finditer(pattern, text, re.IGNORECASE):
        # Extract just the name part, not the relationship
        name_start = match.start(2)
        name_end = match.end(2)
        name = match.group(2)
        
        entities.append(PHIEntity(
            start=name_start,
            end=name_end,
            category="NAME",
            confidence=0.85,
            text=name
        ))
    
    return entities


def detect_ages_over_89(text: str) -> List[PHIEntity]:
    """
    Detect ages ≥ 89 in clinical notes, which require special handling per HIPAA.
    
    Args:
        text: The clinical note text
        
    Returns:
        List of detected PHI entities
    """
    entities = []
    
    # Pattern for "XX-year-old" or "XX year old"
    age_pattern = r"\b(\d{2,3})[\s-](?:years?[\s-]old|y\.?o\.?|years?[\s-]of[\s-]age)\b"
    
    for match in re.finditer(age_pattern, text, re.IGNORECASE):
        age = int(match.group(1))
        if age >= 90:  # HIPAA requires special handling for ages ≥ 90
            entities.append(PHIEntity(
                start=match.start(1),
                end=match.end(1),
                category="AGE_OVER_89",
                confidence=1.0,
                text=match.group(1)
            ))
    
    return entities


def is_clinical_measurement(text: str) -> bool:
    """
    Check if text represents a clinical measurement that should not be redacted.
    
    Args:
        text: Text to check
        
    Returns:
        True if the text is a clinical measurement, False otherwise
    """
    # Vital sign patterns
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
    ]
    
    # Lab value patterns
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
    ]
    
    # Medication dose patterns
    medication_patterns = [
        r"\b\d{1,3}(?:\.\d+)?\s*mg\b",           # Milligrams
        r"\b\d{1,3}(?:\.\d+)?\s*mcg\b",          # Micrograms
        r"\b\d{1,3}(?:\.\d+)?\s*units?\b",       # Units
        r"\b\d{1,3}(?:\.\d+)?\s*ml\b",           # Milliliters
        r"\b\d{1,3}(?:\.\d+)?\s*cc\b",           # Cubic centimeters
        r"\b\d{1,3}(?:\.\d+)?\s*drops?\b",       # Drops
        r"\b\d{1,3}(?:\.\d+)?\s*tablets?\b",     # Tablets
        r"\b\d{1,3}(?:\.\d+)?\s*capsules?\b",    # Capsules
        r"\b\d{1,3}(?:\.\d+)?\s*g\b",            # Grams
        r"\b\d{1,3}(?:\.\d+)?\s*kg\b",           # Kilograms
        r"\b\d{1,3}(?:\.\d+)?\s*mmol\b",         # Millimoles
        r"\b\d{1,3}(?:\.\d+)?\s*mEq\b",          # Milliequivalents
        r"\b\d{1,3}(?:\.\d+)?\s*µg\b",           # Micrograms (Unicode)
        r"\b\d{1,3}(?:\.\d+)?\s*IU\b",           # International Units
        r"\b\d{1,3}(?:\.\d+)?\s*mIU\b",          # Milli-International Units
        r"\b\d{1,3}(?:\.\d+)?\s*%\b",            # Percentage
        # Common medication context patterns
        r"(?:Metoprolol|Aspirin|Atorvastatin|Clopidogrel|Lisinopril|Amlodipine|Furosemide|Warfarin)\s+\d{1,3}(?:\.\d+)?\s*mg",
        r"(?:succinate|tartrate|maleate|hydrochloride)\s+\d{1,3}(?:\.\d+)?\s*mg",
        r"\b\d{1,3}(?:\.\d+)?\s*mg\s+PO\b",      # Oral medications
        r"\b\d{1,3}(?:\.\d+)?\s*mg\s+IV\b",      # IV medications
        r"\b\d{1,3}(?:\.\d+)?\s*mg\s+(?:daily|BID|TID|QID|qhs|q\d+h)\b", # With frequency
    ]
    
    # Medical term patterns (common medical abbreviations and terms)
    medical_term_patterns = [
        r"\bNSTEMI\b",                 # Non-ST elevation myocardial infarction
        r"\bSTEMI\b",                  # ST elevation myocardial infarction
        r"\bCABG\b",                   # Coronary artery bypass graft
        r"\bMI\b",                     # Myocardial infarction
        r"\bCHF\b",                    # Congestive heart failure
        r"\bCOPD\b",                   # Chronic obstructive pulmonary disease
        r"\bDM\b",                     # Diabetes mellitus
        r"\bHTN\b",                    # Hypertension
        r"\bCAD\b",                    # Coronary artery disease
        r"\bAFib\b",                   # Atrial fibrillation
        r"\bPOD\b",                    # Post-operative day
        r"\bPO\b",                     # Per os (by mouth)
        r"\bIV\b",                     # Intravenous
        r"\bIM\b",                     # Intramuscular
        r"\bSC\b",                     # Subcutaneous
    ]
    
    # Check if text matches any of the patterns
    all_patterns = vital_patterns + lab_patterns + medication_patterns + medical_term_patterns
    for pattern in all_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False


def detect_long_numeric_ids(text: str, existing_entities: List[PHIEntity]) -> List[PHIEntity]:
    """
    Detect long numeric identifiers not already caught by other detectors.
    
    Args:
        text: The clinical note text
        existing_entities: List of already detected entities
        
    Returns:
        List of detected PHI entities
    """
    entities = []
    
    # Pattern for 8+ digit numbers (increased threshold to avoid single digits)
    long_number_pattern = r"\b\d{8,}\b"
    
    # Create a set of spans that are already covered by existing entities
    covered_spans = set()
    for entity in existing_entities:
        for i in range(entity.start, entity.end):
            covered_spans.add(i)
    
    # Find long numbers
    for match in re.finditer(long_number_pattern, text):
        # Check if this span overlaps with any existing entity
        overlapped = False
        for i in range(match.start(), match.end()):
            if i in covered_spans:
                overlapped = True
                break
        
        if not overlapped:
            # Check if it's a clinical measurement (which should not be redacted)
            context_start = max(0, match.start() - 10)
            context_end = min(len(text), match.end() + 10)
            context = text[context_start:context_end]
            
            # Additional context checks to avoid false positives
            if not is_clinical_measurement(context):
                # Skip if it's part of a date (YYYY format)
                if re.search(r'\b(19|20)\d{2}\b', match.group()):
                    continue
                # Skip if it's part of a phone number
                if re.search(r'\(\d{3}\)\s*\d{3}-\d{4}', context):
                    continue
                # Skip if it's part of a ZIP code
                if re.search(r'\b\d{5}-\d{4}\b', context):
                    continue
                
                entities.append(PHIEntity(
                    start=match.start(),
                    end=match.end(),
                    category="OTHER_ID",
                    confidence=0.75,
                    text=match.group()
                ))
    
    return entities


def detect_clinical_phi(text: str, existing_entities: List[PHIEntity] = None) -> List[PHIEntity]:
    """
    Detect PHI in clinical notes using specialized patterns.
    
    Args:
        text: The clinical note text
        existing_entities: List of already detected entities
        
    Returns:
        List of detected PHI entities
    """
    if existing_entities is None:
        existing_entities = []
    
    entities = []
    
    # Check if this is a clinical note by looking for common clinical note headers
    # This helps avoid applying clinical patterns to non-clinical text
    is_clinical_note = False
    clinical_headers = [
        r"patient\s*(?:name|id|information|record)",
        r"medical\s*record",
        r"admission|discharge",
        r"diagnosis",
        r"procedure",
        r"hospital\s*course",
        r"medications",
        r"follow-?up",
        r"clinical\s*note",
        r"assessment",
        r"plan",
        r"history\s*(?:of|and)\s*physical",
        r"progress\s*note"
    ]
    
    for header in clinical_headers:
        if re.search(header, text, re.IGNORECASE):
            is_clinical_note = True
            break
    
    # Only apply clinical detectors if this appears to be a clinical note
    if is_clinical_note:
        entities.extend(detect_section_headers(text))
        entities.extend(detect_initials_and_nicknames(text))
        entities.extend(detect_facility_names(text))
        entities.extend(detect_relatives_and_contacts(text))
        entities.extend(detect_ages_over_89(text))
        
        # Apply catch-all detector for long numeric IDs
        # This should be applied last to avoid catching numbers already detected
        all_entities = existing_entities + entities
        entities.extend(detect_long_numeric_ids(text, all_entities))
    
    return entities

