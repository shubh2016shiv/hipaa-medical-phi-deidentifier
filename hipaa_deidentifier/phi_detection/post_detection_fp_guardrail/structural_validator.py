"""
Presidio Structural Validator — Validates Presidio spaCy entities by structure.

Architecture:
-------------
    ┌─────────────────────────┐     ┌──────────────────────────────┐
    │  FalsePositiveGuardrail │────▶│  PresidioStructuralValidator │
    │  (fp_guardrail.py)      │     │  (structural_validator.py)   │
    └─────────────────────────┘     └──────────────────────────────┘

    Presidio's spaCy NER assigns a flat 0.85 to every detection regardless
    of actual confidence.  Structural validation compensates by running the
    entity text through the same regex patterns that the custom recognizers
    use during detection.

    Strategy:
      - Entities from non-Presidio sources → pass through (handled elsewhere)
      - Presidio entities with confidence >= 0.95 → already pattern-validated
        by a custom recognizer (SSN, MRN, Date…) → pass through
      - Presidio entities with confidence < 0.95  → apply category regex
      - NAME / ORGANIZATION → pass through (NameOrganizationContextFilter
        handles those downstream)
      - Unknown category    → pass through (safe default)

    Patterns are imported directly from the recogniser class attributes so
    that a single source of truth is maintained.

Dependencies:
    - recognizer/date_recognizer.py        — DateRecognizer.DATE_PATTERNS
    - recognizer/ssn_recognizer.py         — SSNRecognizer.SSN_PATTERNS
    - recognizer/mrn_recognizer.py         — MRNRecognizer.MRN_PATTERNS
    - recognizer/us_location_recognizer.py — USLocationRecognizer.LOCATION_PATTERNS
    - recognizer/account_number_recognizer.py — AccountNumberRecognizer patterns
    - recognizer/age_over_89_recognizer.py  — AgeOver89Recognizer patterns
    - recognizer/biometric_id_recognizer.py — BiometricIDRecognizer patterns
    - recognizer/device_id_recognizer.py   — DeviceIDRecognizer patterns
    - recognizer/encounter_id_recognizer.py — EncounterIDRecognizer patterns
    - recognizer/health_plan_id_recognizer.py — HealthPlanIDRecognizer patterns
    - recognizer/photo_id_recognizer.py    — PhotoIDRecognizer patterns
    - recognizer/vehicle_id_recognizer.py  — VehicleIDRecognizer patterns
    - recognizer/recognizer_config.py      — RecognizerPatterns, RecognizerThresholds
    - models/phi_entity.py                 — PHIEntity dataclass
    - utils/logger.py                      — Structured logging

Author: HIPAA De-identification System
Last Updated: 2026-05-03
"""

from __future__ import annotations

import logging
import re
from typing import Dict, FrozenSet, List, Sequence

from ...models.phi_entity import PHIEntity
from ..recognizer.account_number_recognizer import AccountNumberRecognizer
from ..recognizer.age_over_89_recognizer import AgeOver89Recognizer
from ..recognizer.biometric_id_recognizer import BiometricIDRecognizer
from ..recognizer.date_recognizer import DateRecognizer
from ..recognizer.device_id_recognizer import DeviceIDRecognizer
from ..recognizer.encounter_id_recognizer import EncounterIDRecognizer
from ..recognizer.health_plan_id_recognizer import HealthPlanIDRecognizer
from ..recognizer.mrn_recognizer import MRNRecognizer
from ..recognizer.photo_id_recognizer import PhotoIDRecognizer
from ..recognizer.recognizer_config import RecognizerPatterns, RecognizerThresholds
from ..recognizer.ssn_recognizer import SSNRecognizer
from ..recognizer.us_location_recognizer import USLocationRecognizer
from ..recognizer.vehicle_id_recognizer import VehicleIDRecognizer

logger = logging.getLogger(__name__)

# Entities whose text has no structural fingerprint — handled by NameOrganizationContextFilter
_UNSTRUCTURED_CATEGORIES: FrozenSet[str] = frozenset({"NAME", "ORGANIZATION"})

# Sources subject to structural validation
_PRESIDIO_SOURCES: FrozenSet[str] = frozenset({"presidio", "presidio_clinical"})

# Confidence at or above this means a custom pattern-recognizer already validated the entity
_CUSTOM_RECOGNIZER_THRESHOLD: float = RecognizerThresholds.VERY_HIGH_CONFIDENCE

# Categories where entity text must contain at least one digit — rules out pure-alpha false positives
# e.g. "accessible" matching the ACC- account-number prefix pattern
_REQUIRE_DIGIT_CATEGORIES: FrozenSet[str] = frozenset(
    {"ACCOUNT_NUMBER", "HEALTH_PLAN_ID", "ENCOUNTER_ID"}
)

# Clock times (07:00 AM) and bare weekday names are not HIPAA Safe Harbor identifiers.
# Keeping them caused spaCy DATE_TIME entities (which include shift times, vital-sign
# timestamps, and scheduling references) to pass structural validation as DATE.
_EXTRA_DATE_PATTERNS: List[str] = []


class PresidioStructuralValidator:
    """Validates low-confidence Presidio entities against category-specific regex.

    Builds a pattern registry at construction time by extracting pattern
    strings directly from the recognizer class attributes, ensuring a single
    source of truth.  Validation is a pure regex search — no Presidio engine
    calls are made at filter time.

    Example:
        >>> validator = PresidioStructuralValidator()
        >>> kept = validator.filter([daily_as_date_entity, real_date_entity], text)
        >>> assert len(kept) == 1
    """

    def __init__(self) -> None:
        """Build the per-category compiled pattern registry."""
        self._category_validators: Dict[str, List[re.Pattern[str]]] = (
            self._build_category_validators()
        )
        logger.info(
            "PresidioStructuralValidator initialised (%d categories)",
            len(self._category_validators),
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def filter(self, entities: Sequence[PHIEntity], _text: str) -> List[PHIEntity]:
        """Apply structural validation and return only valid entities.

        Args:
            entities: Detected PHI entities from all detectors.
            _text: Original document text (reserved for future context checks).

        Returns:
            Entities that pass structural validation, plus all entities
            that are out of scope for this validator.
        """
        validated: List[PHIEntity] = []
        for entity in entities:
            if not self._needs_validation(entity):
                validated.append(entity)
            elif entity.category in _UNSTRUCTURED_CATEGORIES:
                validated.append(entity)  # delegated to NameOrganizationContextFilter
            elif self._is_structurally_valid(entity):
                validated.append(entity)
            else:
                logger.debug("Structural drop: %s '%s'", entity.category, entity.text)
        return validated

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _needs_validation(self, entity: PHIEntity) -> bool:
        """Return True when structural validation should be applied.

        Args:
            entity: The entity to evaluate.

        Returns:
            True for low-confidence Presidio entities.
        """
        source = getattr(entity, "source", "unknown")
        if source not in _PRESIDIO_SOURCES:
            return False
        # Custom recognisers (>=0.95) already performed structural matching
        return entity.confidence < _CUSTOM_RECOGNIZER_THRESHOLD

    def _is_structurally_valid(self, entity: PHIEntity) -> bool:
        """Return True when entity text matches at least one category pattern.

        Args:
            entity: The entity to validate.

        Returns:
            True when a pattern matches, or when no patterns are registered
            for the category (safe-pass for unknown categories).
        """
        if entity.category in _REQUIRE_DIGIT_CATEGORIES and not re.search(
            r"\d", entity.text
        ):
            return False
        patterns = self._category_validators.get(entity.category)
        if patterns is None:
            return True  # unknown category → conservative pass-through
        return any(p.search(entity.text) for p in patterns)

    # ------------------------------------------------------------------
    # Pattern registry construction
    # ------------------------------------------------------------------

    def _build_category_validators(self) -> Dict[str, List[re.Pattern[str]]]:
        """Build the mapping of PHI category → compiled validation patterns.

        Returns:
            Dictionary keyed by category string, value is a list of
            compiled patterns; any match means the entity is structurally valid.
        """
        return {
            "DATE": self._build_date_patterns(),
            "LOCATION": self._build_location_patterns(),
            "US_SSN": self._build_ssn_patterns(),
            "SSN": self._build_ssn_patterns(),
            "MRN": self._build_mrn_patterns(),
            "ACCOUNT_NUMBER": self._build_account_patterns(),
            "DEVICE_ID": self._build_device_patterns(),
            "PHONE_NUMBER": self._build_phone_patterns(),
            "FAX_NUMBER": self._build_phone_patterns(),
            "HEALTH_PLAN_ID": self._build_health_plan_patterns(),
            "ENCOUNTER_ID": self._build_encounter_patterns(),
            "AGE_OVER_89": self._build_age_over_89_patterns(),
            "BIOMETRIC_ID": self._build_biometric_patterns(),
            "PHOTO_ID": self._build_photo_id_patterns(),
            "VEHICLE_ID": self._build_vehicle_id_patterns(),
        }

    def _build_date_patterns(self) -> List[re.Pattern[str]]:
        """Compile date validation patterns from DateRecognizer + time/day extras.

        Returns:
            Compiled patterns covering numeric dates, text-month dates,
            timestamps, and named weekdays.
        """
        all_patterns = DateRecognizer.DATE_PATTERNS + _EXTRA_DATE_PATTERNS
        return [re.compile(p, re.IGNORECASE) for p in all_patterns]

    def _build_location_patterns(self) -> List[re.Pattern[str]]:
        """Compile location validation patterns from USLocationRecognizer.

        Returns:
            Compiled patterns for street addresses, state+ZIP, and ZIP codes.
        """
        return [re.compile(p) for p in USLocationRecognizer.LOCATION_PATTERNS]

    def _build_ssn_patterns(self) -> List[re.Pattern[str]]:
        """Compile SSN validation patterns from SSNRecognizer.

        Returns:
            Compiled patterns enforcing SSA format rules via negative lookahead.
        """
        return [re.compile(p, re.IGNORECASE) for p in SSNRecognizer.SSN_PATTERNS]

    def _build_mrn_patterns(self) -> List[re.Pattern[str]]:
        """Compile MRN validation patterns from MRNRecognizer.

        Returns:
            Compiled patterns covering prefixed, labeled, and numeric MRN formats.
        """
        return [re.compile(p, re.IGNORECASE) for p in MRNRecognizer.MRN_PATTERNS]

    def _build_account_patterns(self) -> List[re.Pattern[str]]:
        """Compile account number patterns from AccountNumberRecognizer instances.

        Returns:
            Compiled patterns requiring a label keyword or known prefix.
        """
        recognizer = AccountNumberRecognizer()
        return [re.compile(p.regex, re.IGNORECASE) for p in recognizer.patterns]

    def _build_device_patterns(self) -> List[re.Pattern[str]]:
        """Compile device ID patterns from DeviceIDRecognizer instances.

        Returns:
            Compiled patterns requiring a device-type keyword or known prefix.
        """
        recognizer = DeviceIDRecognizer()
        return [re.compile(p.regex, re.IGNORECASE) for p in recognizer.patterns]

    def _build_phone_patterns(self) -> List[re.Pattern[str]]:
        """Compile US phone number pattern from RecognizerPatterns.

        Returns:
            Compiled pattern matching standard US 10-digit phone formats.
        """
        return [re.compile(RecognizerPatterns.US_PHONE_PATTERN, re.IGNORECASE)]

    def _build_health_plan_patterns(self) -> List[re.Pattern[str]]:
        """Compile health plan ID patterns from HealthPlanIDRecognizer instances.

        Returns:
            Compiled patterns requiring a label or known insurer prefix.
        """
        recognizer = HealthPlanIDRecognizer()
        return [re.compile(p.regex, re.IGNORECASE) for p in recognizer.patterns]

    def _build_encounter_patterns(self) -> List[re.Pattern[str]]:
        """Compile encounter ID patterns from EncounterIDRecognizer instances.

        Returns:
            Compiled patterns requiring a label or known encounter prefix.
        """
        recognizer = EncounterIDRecognizer()
        return [re.compile(p.regex, re.IGNORECASE) for p in recognizer.patterns]

    def _build_age_over_89_patterns(self) -> List[re.Pattern[str]]:
        """Compile age-over-89 patterns from AgeOver89Recognizer instances.

        Returns:
            Compiled patterns covering labeled age keywords, years-old forms,
            and birth-year ranges that imply age > 89.
        """
        recognizer = AgeOver89Recognizer()
        return [re.compile(p.regex, re.IGNORECASE) for p in recognizer.patterns]

    def _build_biometric_patterns(self) -> List[re.Pattern[str]]:
        """Compile biometric ID patterns from BiometricIDRecognizer instances.

        Returns:
            Compiled patterns requiring a biometric keyword label.
        """
        recognizer = BiometricIDRecognizer()
        return [re.compile(p.regex, re.IGNORECASE) for p in recognizer.patterns]

    def _build_photo_id_patterns(self) -> List[re.Pattern[str]]:
        """Compile photo ID patterns from PhotoIDRecognizer instances.

        Returns:
            Compiled patterns covering image file references and photo labels.
        """
        recognizer = PhotoIDRecognizer()
        return [re.compile(p.regex, re.IGNORECASE) for p in recognizer.patterns]

    def _build_vehicle_id_patterns(self) -> List[re.Pattern[str]]:
        """Compile vehicle ID patterns from VehicleIDRecognizer instances.

        Returns:
            Compiled patterns covering VINs and labeled license plates.
        """
        recognizer = VehicleIDRecognizer()
        return [re.compile(p.regex, re.IGNORECASE) for p in recognizer.patterns]
