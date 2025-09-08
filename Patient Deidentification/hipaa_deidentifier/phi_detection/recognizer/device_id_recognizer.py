"""
Device ID Recognizer for HIPAA De-identification
"""

import regex as re
from presidio_analyzer import Pattern, PatternRecognizer


class DeviceIDRecognizer(PatternRecognizer):
    """
    Recognizes medical device identifiers.
    """
    def __init__(self, name="DEVICE_ID", supported_entity="DEVICE_ID", patterns=None):
        if patterns is None:
            patterns = [
                # Device ID with explicit label
                Pattern(
                    "device_id_labeled",
                    r"\b(?:Device\s*ID|Medical\s*Device|Serial\s*[#]?|Equipment\s*ID)\s*[:#=\-]?\s*([A-Z0-9\-]{3,20})\b",
                    0.95
                ),
                # Medical device format with PM prefix (pacemaker)
                Pattern(
                    "pacemaker_id",
                    r"\bPM[-#]([A-Z0-9\-]{4,15})\b",
                    0.9
                ),
                # Serial number format
                Pattern(
                    "serial_number",
                    r"\bSN[-#]([A-Z0-9\-]{4,15})\b",
                    0.9
                ),
                # Generic medical device format
                Pattern(
                    "generic_device_id",
                    r"\b(?:Device|Equipment|Implant|Prosthetic)\s*[:#=\-]?\s*([A-Z0-9\-]{4,20})\b",
                    0.8
                ),
            ]
        super().__init__(supported_entity=supported_entity, patterns=patterns)

