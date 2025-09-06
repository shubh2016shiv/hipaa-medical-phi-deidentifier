"""
Custom PHI Recognizers

Defines custom recognizers for healthcare-specific PHI elements like
Medical Record Numbers (MRN), Encounter IDs, and ages over 89.
"""
import regex as re
from presidio_analyzer import Pattern, PatternRecognizer


class MedicalRecordNumberRecognizer(PatternRecognizer):
    """
    Recognizes Medical Record Numbers (MRNs) in various formats.
    
    MRNs are hospital-specific patient identifiers that must be
    de-identified under HIPAA.
    """
    def __init__(self, name="MRN", supported_entity="MRN", patterns=None):
        if patterns is None:
            patterns = [
                # MRN with explicit label - high confidence
                Pattern(
                    "mrn_labeled", 
                    r"\b(?:MRN|Med(?:ical)?\s*Record\s*(?:Number|No\.?)|Chart\s*(?:Number|No\.?))\s*[:#=\-]?\s*([A-Z0-9]{6,12})\b", 
                    0.95
                ),
                # MRN with hash/pound sign prefix - high confidence
                Pattern(
                    "mrn_hash_prefix",
                    r"\b(?:MRN|Med(?:ical)?\s*Record|Chart)?\s*#\s*([A-Z0-9]{6,12})\b",
                    0.9
                ),
                # MRN in specific formats commonly used - medium-high confidence
                Pattern(
                    "mrn_formatted",
                    r"\b([A-Z]{1,3}[-]?[0-9]{6,10})\b",  # Format like MR-1234567
                    0.75
                ),
                # Standalone MRN with context - medium confidence
                Pattern(
                    "mrn_with_context",
                    r"(?:patient|record|chart|account)(?:\s+(?:id|identification|number))?\s*[:#]?\s*([A-Z0-9]{6,12})\b",
                    0.65
                ),
                # Standalone MRN (lower confidence since it could be another number)
                # Only include if in a context where it's likely to be an MRN
                Pattern(
                    "mrn_numeric",  
                    r"(?<=Patient)(?:\s+(?:ID|Number))?\s*[:#]?\s*([0-9]{7,10})\b", 
                    0.5
                ),
            ]
        super().__init__(supported_entity=supported_entity, patterns=patterns)


class EncounterIdentifierRecognizer(PatternRecognizer):
    """
    Recognizes hospital encounter/visit identifiers.
    
    Encounter IDs are visit-specific identifiers that must be
    de-identified under HIPAA.
    """
    def __init__(self, name="ENCOUNTER_ID", supported_entity="ENCOUNTER_ID", patterns=None):
        if patterns is None:
            patterns = [
                # Explicit encounter ID labels - high confidence
                Pattern(
                    "encounter_id", 
                    r"\b(?:Encounter(?:\s*ID)?|Visit(?:\s*ID)?|Admission(?:\s*ID)?)\s*[:#=\-]?\s*([A-Z0-9\-]{6,18})\b", 
                    0.95
                ),
                # Visit number formats - high confidence
                Pattern(
                    "visit_number",
                    r"\bVisit\s*(?:Number|No\.?|#)\s*[:#=\-]?\s*([A-Z0-9\-]{6,18})\b",
                    0.9
                ),
                # Common encounter ID formats - medium-high confidence
                Pattern(
                    "enc_formatted",
                    r"\b(?:ENC|VST|ADM)[-]?([0-9]{6,12}(?:-[0-9]{1,4})?)\b",  # Format like ENC-1234567 or ENC-1234567-001
                    0.85
                ),
                # Date-based encounter IDs - medium confidence
                Pattern(
                    "date_encounter",
                    r"\bENC[-]?([0-9]{8}[-][0-9]{3,6})\b",  # Format like ENC-20230101-12345
                    0.8
                ),
                # Context-based encounter IDs - medium confidence
                Pattern(
                    "context_encounter",
                    r"(?:admitted|admission|visit|encounter)\s+(?:on|at|for|number)?\s*[:#]?\s*([A-Z0-9\-]{6,18})\b",
                    0.7
                ),
            ]
        super().__init__(supported_entity=supported_entity, patterns=patterns)


class AgeOver89Recognizer(PatternRecognizer):
    """
    Recognizes ages over 89, which must be de-identified under HIPAA.
    
    HIPAA Safe Harbor requires ages over 89 to be generalized to a category
    such as "90+" rather than the specific age.
    """
    def __init__(self, name="AGE_OVER_89", supported_entity="AGE_OVER_89", patterns=None):
        if patterns is None:
            patterns = [
                # Explicit age statements - high confidence
                Pattern(
                    "age_over_89", 
                    r"\b(?:age|aged?)\s*[:\-=]?\s*(9[0-9]|1[0-9]{2,})\b", 
                    0.95
                ),
                # Years old format - high confidence
                Pattern(
                    "years_old_over_89",
                    r"\b(9[0-9]|1[0-9]{2,})\s*(?:years?\s*old|y\.?o\.?|years?\s*of\s*age)\b",
                    0.95
                ),
                # Age in parentheses - medium-high confidence
                Pattern(
                    "age_parentheses",
                    r"\((?:age|aged?)?:?\s*(9[0-9]|1[0-9]{2,})\)",
                    0.9
                ),
                # Age with context - medium-high confidence
                Pattern(
                    "age_with_context",
                    r"(?:patient|individual|person|male|female|man|woman)\s+(?:is|aged?|of age)\s*(9[0-9]|1[0-9]{2,})",
                    0.85
                ),
                # Birth year indicating age over 89 (based on current year)
                Pattern(
                    "birth_year_over_89",
                    r"\b(?:born|birth|DOB|date of birth).*(?:18[0-9]{2}|19[0-2][0-9])\b",
                    0.8
                ),
            ]
        super().__init__(supported_entity=supported_entity, patterns=patterns)


