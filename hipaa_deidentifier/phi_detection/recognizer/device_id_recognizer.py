"""
Device ID Recognizer

Recognizes medical device identifiers and serial numbers.
Part of HIPAA Safe Harbor identifier #13: Device identifiers and serial numbers.

Enterprise Features:
- Medical device-specific patterns
- Serial number detection
- Configurable confidence thresholds
- Professional logging

Author: HIPAA De-identification System
Version: 2.0.0 (Refactored for enterprise standards)
"""

from typing import List

from presidio_analyzer import Pattern, PatternRecognizer

from ...utils.logger import get_logger
from .recognizer_config import RecognizerThresholds

# Initialize module logger
logger = get_logger("recognizer.device")


class DeviceIDRecognizer(PatternRecognizer):
    """
    Recognizes medical device identifiers.

    Detects patterns such as:
    - Device ID: PM-12345 (pacemaker)
    - Serial Number: SN-ABC123
    - Medical Device: MD-9876543

    Features:
    - Context-aware detection
    - Multiple device type support
    - High confidence scoring
    """

    def __init__(
        self,
        name: str = "DEVICE_ID",
        supported_entity: str = "DEVICE_ID",
        patterns: List[Pattern] = None,
    ):
        """
        Initialize the device ID recognizer.

        Args:
            name: Recognizer name for logging
            supported_entity: Entity type this recognizer detects
            patterns: Optional custom patterns (uses defaults if None)
        """
        if patterns is None:
            patterns = [
                # Device ID with explicit label - very high confidence
                Pattern(
                    "device_id_labeled",
                    r"\b(?:Device\s*ID|Medical\s*Device|Serial\s*[#]?|Equipment\s*ID)\s*[:#=\-]?\s*([A-Z0-9\-]{3,20})\b",
                    RecognizerThresholds.VERY_HIGH_CONFIDENCE,
                ),
                # Medical device format with PM prefix (pacemaker) - high confidence
                Pattern(
                    "pacemaker_id",
                    r"\bPM[-#]([A-Z0-9\-]{4,15})\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                # Serial number format - high confidence
                Pattern(
                    "serial_number",
                    r"\bSN[-#]([A-Z0-9\-]{4,15})\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                # Generic medical device format - medium confidence
                Pattern(
                    "generic_device_id",
                    r"\b(?:Device|Equipment|Implant|Prosthetic)\s*[:#=\-]?\s*([A-Z0-9\-]{4,20})\b",
                    RecognizerThresholds.MEDIUM_CONFIDENCE,
                ),
            ]

        super().__init__(
            supported_entity=supported_entity, patterns=patterns, name=name
        )
        logger.info(f"DeviceIDRecognizer initialized with {len(patterns)} patterns")
