"""
Photo ID Recognizer

Recognizes photo identifiers and image file references.
Part of HIPAA Safe Harbor identifier #16: Full-face photographs and comparable images.

Enterprise Features:
- Image file format detection
- Photo reference pattern matching
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
logger = get_logger("recognizer.photo")


class PhotoIDRecognizer(PatternRecognizer):
    """
    Recognizes photo identifiers and image references.

    Detects patterns such as:
    - face_photo_12345.jpg
    - Photo ID: patient_001.png
    - Patient photo on file

    Features:
    - Image file extension detection
    - Photo reference contexts
    - High confidence scoring
    """

    def __init__(
        self,
        name: str = "PHOTO_ID",
        supported_entity: str = "PHOTO_ID",
        patterns: List[Pattern] | None = None,
    ):
        """
        Initialize the photo ID recognizer.

        Args:
            name: Recognizer name for logging
            supported_entity: Entity type this recognizer detects
            patterns: Optional custom patterns (uses defaults if None)
        """
        if patterns is None:
            patterns = [
                # Photo file references with common image extensions - very high confidence
                Pattern(
                    "photo_file_reference",
                    r"\b(?:face|photo|image|picture|portrait|photograph)_\w+\.(?:jpg|jpeg|png|gif|tiff|bmp)\b",
                    RecognizerThresholds.VERY_HIGH_CONFIDENCE,
                ),
                # Photo with explicit label - high confidence
                Pattern(
                    "photo_labeled",
                    r"\b(?:Photo|Image|Picture|Portrait|Photograph|Face\s*Photo)\s*(?:ID|#|:)?\s*[:#=\-]?\s*([A-Za-z0-9\-_\.]{3,30})\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                # Image file path or reference - high confidence
                Pattern(
                    "image_file_path",
                    r"\b(?:Image|Photo|Picture):\s*([A-Za-z0-9\-_\.]{3,30}\.(?:jpg|jpeg|png|gif|tiff|bmp))\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                # Patient photo references - medium-high confidence
                Pattern(
                    "patient_photo",
                    r"\bPatient\s*(?:photo|image|picture)\s*(?:on\s*file|attached|included)\b",
                    RecognizerThresholds.MEDIUM_HIGH_CONFIDENCE,
                ),
            ]

        super().__init__(
            supported_entity=supported_entity, patterns=patterns, name=name
        )
        logger.info(f"PhotoIDRecognizer initialized with {len(patterns)} patterns")
