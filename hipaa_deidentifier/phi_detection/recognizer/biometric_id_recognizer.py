"""
Biometric ID Recognizer — Detects biometric identifier references.

Architecture:
-------------
    ┌─────────────────────────┐     ┌──────────────────────────────┐
    │  PresidioIdentifier     │────▶│  BiometricIDRecognizer       │
    │  (identifier/)          │     │  (recognizer/)               │
    └─────────────────────────┘     └──────────────────────────────┘

    Registered with Presidio's AnalyzerEngine registry.
    Fires on BIOMETRIC_ID entity type.

    Covers HIPAA Safe Harbor identifier #17: biometric identifiers
    (fingerprints, retina scans, voice prints, etc.).

Dependencies:
    - recognizer_config.py  — RecognizerThresholds constants
    - utils/logger.py       — Structured logging

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

from typing import List, Optional

from presidio_analyzer import Pattern, PatternRecognizer

from ...utils.logger import get_logger
from .recognizer_config import RecognizerThresholds

logger = get_logger("recognizer.biometric_id")


class BiometricIDRecognizer(PatternRecognizer):
    """Recognizes biometric identifier references in clinical text.

    Detects patterns such as:
    - Fingerprint ID: FP-12345
    - Biometric Data: BIO-ABC987
    - Retina Scan ID: RS-XYZ001

    Example:
        >>> recognizer = BiometricIDRecognizer()
        >>> results = recognizer.analyze("Fingerprint ID: FP-12345", ["BIOMETRIC_ID"], None)
        >>> print(len(results))
        1
    """

    def __init__(
        self,
        name: str = "BIOMETRIC_ID",
        supported_entity: str = "BIOMETRIC_ID",
        patterns: Optional[List[Pattern]] = None,
    ) -> None:
        """Initialize the biometric ID recognizer.

        Args:
            name: Recognizer name for Presidio registry.
            supported_entity: Entity type emitted on detection.
            patterns: Optional custom patterns; defaults are used when None.
        """
        if patterns is None:
            patterns = [
                Pattern(
                    "biometric_id_labeled",
                    r"\b(?:Fingerprint|Retina\s*Scan|Iris\s*Scan|Voice\s*Print|Face\s*Scan|DNA|Biometric)\s*(?:ID|#|Number|Data)?\s*[:#=\-]?\s*([A-Z0-9\-]{3,20})\b",
                    RecognizerThresholds.HIGH_CONFIDENCE,
                ),
                Pattern(
                    "biometric_data_labeled",
                    r"\bBiometric\s*(?:ID|Data|Information|Identifier)\s*[:#=\-]?\s*([A-Z0-9\-]{3,20})\b",
                    RecognizerThresholds.MEDIUM_HIGH_CONFIDENCE,
                ),
            ]

        super().__init__(supported_entity=supported_entity, patterns=patterns, name=name)
        logger.info("BiometricIDRecognizer initialized with %d patterns", len(patterns))
