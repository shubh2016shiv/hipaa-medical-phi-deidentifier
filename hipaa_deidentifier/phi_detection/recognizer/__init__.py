"""
PHI Recognizer Package — Presidio pattern recognizers for all 18 HIPAA Safe Harbor identifiers.

Architecture:
-------------
    ┌─────────────────────────┐
    │  PresidioIdentifier     │  registers all recognizers below into AnalyzerEngine
    │  (identifier/)          │
    └────────────┬────────────┘
                 │
    ┌────────────▼────────────────────────────────────────────────────────────┐
    │  recognizer/                                                            │
    │                                                                         │
    │  Clinical identifiers          Structured identifiers                   │
    │  ├── mrn_recognizer            ├── ssn_recognizer                       │
    │  ├── encounter_id_recognizer   ├── date_recognizer                      │
    │  └── age_over_89_recognizer    └── fax_recognizer                       │
    │                                                                         │
    │  HIPAA Safe Harbor identifiers          Location                        │
    │  ├── health_plan_id_recognizer          └── us_location_recognizer      │
    │  ├── vehicle_id_recognizer                                              │
    │  ├── biometric_id_recognizer            Shared config                   │
    │  ├── photo_id_recognizer                └── recognizer_config           │
    │  ├── device_id_recognizer                                               │
    │  └── account_number_recognizer                                          │
    └─────────────────────────────────────────────────────────────────────────┘

Naming convention: one file = one recognizer class, named after the entity it detects.
All recognizers follow the same Gen 2 style: PatternRecognizer or EntityRecognizer
subclass, RecognizerThresholds constants (no magic numbers), structured logging.

Dependencies:
    - recognizer_config.py  — shared thresholds and domain constants
    - utils/logger.py       — structured logging

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from .mrn_recognizer import MRNRecognizer
from .encounter_id_recognizer import EncounterIDRecognizer
from .age_over_89_recognizer import AgeOver89Recognizer
from .ssn_recognizer import SSNRecognizer
from .date_recognizer import DateRecognizer
from .fax_recognizer import FaxRecognizer
from .photo_id_recognizer import PhotoIDRecognizer
from .device_id_recognizer import DeviceIDRecognizer
from .account_number_recognizer import AccountNumberRecognizer
from .health_plan_id_recognizer import HealthPlanIDRecognizer
from .vehicle_id_recognizer import VehicleIDRecognizer
from .biometric_id_recognizer import BiometricIDRecognizer
from .us_location_recognizer import USLocationRecognizer

__all__ = [
    "MRNRecognizer",
    "EncounterIDRecognizer",
    "AgeOver89Recognizer",
    "SSNRecognizer",
    "DateRecognizer",
    "FaxRecognizer",
    "PhotoIDRecognizer",
    "DeviceIDRecognizer",
    "AccountNumberRecognizer",
    "HealthPlanIDRecognizer",
    "VehicleIDRecognizer",
    "BiometricIDRecognizer",
    "USLocationRecognizer",
]
