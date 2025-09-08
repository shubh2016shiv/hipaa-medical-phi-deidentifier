"""
Photo ID Recognizer for HIPAA De-identification
"""

import regex as re
from presidio_analyzer import Pattern, PatternRecognizer


class PhotoIDRecognizer(PatternRecognizer):
    """
    Recognizes photo identifiers and image references.
    """
    def __init__(self, name="PHOTO_ID", supported_entity="PHOTO_ID", patterns=None):
        if patterns is None:
            patterns = [
                # Photo file references with common image extensions
                Pattern(
                    "photo_file_reference",
                    r"\b(?:face|photo|image|picture|portrait|photograph)_\w+\.(?:jpg|jpeg|png|gif|tiff|bmp)\b",
                    0.95
                ),
                # Photo with explicit label
                Pattern(
                    "photo_labeled",
                    r"\b(?:Photo|Image|Picture|Portrait|Photograph|Face\s*Photo)\s*(?:ID|#|:)?\s*[:#=\-]?\s*([A-Za-z0-9\-_\.]{3,30})\b",
                    0.9
                ),
                # Image file path or reference
                Pattern(
                    "image_file_path",
                    r"\b(?:Image|Photo|Picture):\s*([A-Za-z0-9\-_\.]{3,30}\.(?:jpg|jpeg|png|gif|tiff|bmp))\b",
                    0.9
                ),
                # Patient photo references
                Pattern(
                    "patient_photo",
                    r"\bPatient\s*(?:photo|image|picture)\s*(?:on\s*file|attached|included)\b",
                    0.85
                ),
            ]
        super().__init__(supported_entity=supported_entity, patterns=patterns)

