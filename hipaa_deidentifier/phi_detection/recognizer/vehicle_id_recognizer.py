"""
Vehicle ID Recognizer — Detects vehicle identifiers including VINs and license plates.

Architecture:
-------------
    ┌─────────────────────────┐     ┌──────────────────────────┐
    │  PresidioIdentifier     │────▶│  VehicleIDRecognizer     │
    │  (identifier/)          │     │  (recognizer/)           │
    └─────────────────────────┘     └──────────────────────────┘

    Registered with Presidio's AnalyzerEngine registry.
    Fires on VEHICLE_ID entity type.

    Covers HIPAA Safe Harbor identifier #14: vehicle identifiers and serial numbers.

Dependencies:
    - recognizer_config.py  — RecognizerThresholds, IdentifierConfig constants
    - utils/logger.py       — Structured logging

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

from typing import List, Optional

from presidio_analyzer import Pattern, PatternRecognizer

from ...utils.logger import get_logger
from .recognizer_config import RecognizerThresholds

logger = get_logger("recognizer.vehicle_id")


class VehicleIDRecognizer(PatternRecognizer):
    """Recognizes vehicle identifiers such as VINs and license plates.

    Detects patterns such as:
    - VIN: 1HGBH41JXMN109186
    - License Plate: ABC-1234
    - Vehicle ID: 1HGBH41JXMN109186

    Example:
        >>> recognizer = VehicleIDRecognizer()
        >>> results = recognizer.analyze("VIN: 1HGBH41JXMN109186", ["VEHICLE_ID"], None)
        >>> print(len(results))
        1
    """

    def __init__(
        self,
        name: str = "VEHICLE_ID",
        supported_entity: str = "VEHICLE_ID",
        patterns: Optional[List[Pattern]] = None,
    ) -> None:
        """Initialize the vehicle ID recognizer.

        Args:
            name: Recognizer name for Presidio registry.
            supported_entity: Entity type emitted on detection.
            patterns: Optional custom patterns; defaults are used when None.
        """
        if patterns is None:
            patterns = [
                Pattern(
                    "vin_labeled",
                    r"\b(?:VIN|Vehicle\s*ID)\s*[:#=\-]?\s*([A-Z0-9]{17})\b",
                    RecognizerThresholds.VERY_HIGH_CONFIDENCE,
                ),
                # Standard 17-character VIN without a label — lower confidence to reduce false positives
                Pattern(
                    "vin_unlabeled",
                    r"\b([A-HJ-NPR-Z0-9]{17})\b",
                    RecognizerThresholds.LOW_CONFIDENCE,
                ),
                Pattern(
                    "license_plate_labeled",
                    r"\b(?:License\s*Plate|Plate\s*(?:Number|#))\s*[:#=\-]?\s*([A-Z0-9\-\s]{5,10})\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
            ]

        super().__init__(supported_entity=supported_entity, patterns=patterns, name=name)
        logger.info("VehicleIDRecognizer initialized with %d patterns", len(patterns))
