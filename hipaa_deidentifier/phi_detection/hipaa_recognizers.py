"""
HIPAA-specific PHI Recognizers

Defines custom recognizers for all 18 HIPAA Safe Harbor identifiers.
"""
import regex as re
from presidio_analyzer import Pattern, PatternRecognizer


class HealthPlanIDRecognizer(PatternRecognizer):
    """
    Recognizes health plan beneficiary numbers.
    """
    def __init__(self, name="HEALTH_PLAN_ID", supported_entity="HEALTH_PLAN_ID", patterns=None):
        if patterns is None:
            patterns = [
                # Health plan ID with explicit label
                Pattern(
                    "health_plan_id_labeled",
                    r"\b(?:Health\s*Plan(?:\s*ID)?|Insurance(?:\s*ID)?|Member(?:\s*ID)?)\s*[:#=\-]?\s*([A-Z0-9\-]{6,20})\b",
                    0.9
                ),
                # Common health plan ID formats
                Pattern(
                    "health_plan_id_format",
                    r"\b(?:BCBS|UHC|AETNA|CIGNA|HUMANA|ANTHEM)[\-]([A-Z0-9\-]{6,12})\b",
                    0.85
                ),
                # Generic member ID format
                Pattern(
                    "member_id_format",
                    r"\bMember\s*(?:ID|Number|#)?\s*[:#=\-]?\s*([A-Z0-9\-]{6,20})\b",
                    0.8
                ),
            ]
        super().__init__(supported_entity=supported_entity, patterns=patterns)


class VehicleIDRecognizer(PatternRecognizer):
    """
    Recognizes vehicle identifiers like VINs and license plates.
    """
    def __init__(self, name="VEHICLE_ID", supported_entity="VEHICLE_ID", patterns=None):
        if patterns is None:
            patterns = [
                # Vehicle Identification Number (VIN)
                Pattern(
                    "vin_format",
                    r"\b(?:VIN|Vehicle\s*ID)\s*[:#=\-]?\s*([A-Z0-9]{17})\b",
                    0.95
                ),
                # VIN without label but in standard format
                Pattern(
                    "vin_standard",
                    r"\b([A-HJ-NPR-Z0-9]{17})\b",
                    0.7
                ),
                # License plate
                Pattern(
                    "license_plate",
                    r"\b(?:License\s*Plate|Plate\s*Number|Plate\s*#)\s*[:#=\-]?\s*([A-Z0-9\-\s]{5,10})\b",
                    0.9
                ),
            ]
        super().__init__(supported_entity=supported_entity, patterns=patterns)


class BiometricIDRecognizer(PatternRecognizer):
    """
    Recognizes biometric identifiers.
    """
    def __init__(self, name="BIOMETRIC_ID", supported_entity="BIOMETRIC_ID", patterns=None):
        if patterns is None:
            patterns = [
                # Common biometric references
                Pattern(
                    "biometric_reference",
                    r"\b(?:Fingerprint|Retina\s*Scan|Iris\s*Scan|Voice\s*Print|Face\s*Scan|DNA|Biometric)\s*(?:ID|#|Number|Data)?\s*[:#=\-]?\s*([A-Z0-9\-]{3,20})\b",
                    0.9
                ),
                # Generic biometric mention
                Pattern(
                    "biometric_mention",
                    r"\bBiometric\s*(?:ID|Data|Information|Identifier)\s*[:#=\-]?\s*([A-Z0-9\-]{3,20})\b",
                    0.85
                ),
            ]
        super().__init__(supported_entity=supported_entity, patterns=patterns)


class PhotoIDRecognizer(PatternRecognizer):
    """
    Recognizes photo identifiers.
    """
    def __init__(self, name="PHOTO_ID", supported_entity="PHOTO_ID", patterns=None):
        if patterns is None:
            patterns = [
                # Photo file references
                Pattern(
                    "photo_file",
                    r"\b(?:Photo|Image|Picture|Portrait|Photograph|Face\s*Photo)\s*[:#=\-]?\s*([A-Za-z0-9\-_\.]{3,30}\.(?:jpg|jpeg|png|gif|bmp|tiff))\b",
                    0.9
                ),
                # Photo ID references
                Pattern(
                    "photo_id",
                    r"\b(?:Photo\s*ID|Image\s*ID|Picture\s*ID)\s*[:#=\-]?\s*([A-Z0-9\-]{3,20})\b",
                    0.85
                ),
            ]
        super().__init__(supported_entity=supported_entity, patterns=patterns)


class OtherIDRecognizer(PatternRecognizer):
    """
    Recognizes other unique identifiers.
    """
    def __init__(self, name="OTHER_ID", supported_entity="OTHER_ID", patterns=None):
        if patterns is None:
            patterns = [
                # Custom ID formats
                Pattern(
                    "custom_id",
                    r"\b(?:Custom|Unique|Other|Special|Personal)\s*(?:ID|Identifier|Number|#)\s*[:#=\-]?\s*([A-Z0-9\-]{3,20})\b",
                    0.85
                ),
                # Any ID-like pattern with context
                Pattern(
                    "generic_id",
                    r"\b(?:ID|Identifier|Number)\s*[:#=\-]?\s*([A-Z0-9\-]{6,20})\b",
                    0.7
                ),
            ]
        super().__init__(supported_entity=supported_entity, patterns=patterns)

