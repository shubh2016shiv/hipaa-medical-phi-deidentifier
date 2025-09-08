"""
Account Number Recognizer for HIPAA De-identification
"""

import regex as re
from presidio_analyzer import Pattern, PatternRecognizer


class AccountNumberRecognizer(PatternRecognizer):
    """
    Recognizes account numbers and financial identifiers.
    """
    def __init__(self, name="ACCOUNT_NUMBER", supported_entity="ACCOUNT_NUMBER", patterns=None):
        if patterns is None:
            patterns = [
                # Account number with explicit label
                Pattern(
                    "account_number_labeled",
                    r"\b(?:Account|Acct|Bank|Financial|Payment)\s*(?:Number|ID|#)?\s*[:#=\-]?\s*([A-Z0-9\-]{6,20})\b",
                    0.9
                ),
                # Account number format with ACC prefix
                Pattern(
                    "account_number_format",
                    r"\bACC[-#]?([A-Z0-9\-]{6,15})\b",
                    0.85
                ),
                # Bank account number
                Pattern(
                    "bank_account",
                    r"\bBank\s*(?:Account|Acct|#)?\s*[:#=\-]?\s*([0-9]{8,20})\b",
                    0.8
                ),
            ]
        super().__init__(supported_entity=supported_entity, patterns=patterns)

