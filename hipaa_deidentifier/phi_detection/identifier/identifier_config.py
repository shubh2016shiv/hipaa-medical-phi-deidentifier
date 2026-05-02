#!/usr/bin/env python3
"""
Identifier Configuration Constants

Centralizes all configuration constants used by identifier modules.
Eliminates magic numbers and provides clear documentation for all settings.
"""

from typing import Dict, Set


class DetectionThresholds:
    """Default confidence thresholds for PHI detection."""

    PRESIDIO_DEFAULT = 0.5
    PRESIDIO_HIGH_CONFIDENCE = 0.85
    PRESIDIO_VERY_HIGH_CONFIDENCE = 0.95

    HF_DEFAULT = 0.7
    HF_HIGH_CONFIDENCE = 0.85
    HF_VERY_HIGH_CONFIDENCE = 0.95

    SPACY_DEFAULT = 0.5
    HEADER_PATTERN_DEFAULT = 0.9
    FAX_LABELED = 0.95


class TextProcessing:
    """Configuration for text chunking and processing."""

    HF_CHUNK_SIZE = 500
    HF_CHUNK_OVERLAP = 100
    HF_MIN_CHUNK_LENGTH = 1

    MIN_ENTITY_LENGTH = 1
    MIN_MRN_LENGTH = 3
    MIN_PHONE_DIGITS = 3


class SpacyConfidence:
    """Base confidence scores for different spaCy entity types."""

    PERSON = 0.9
    GPE = 0.85
    LOC = 0.8
    FAC = 0.75
    ORG = 0.85
    DATE = 0.85
    TIME = 0.8
    DEFAULT = 0.7

    MAX_CONFIDENCE = 0.95
    MIN_CONFIDENCE = 0.3
    LENGTH_FACTOR_MULTIPLIER = 0.02
    MAX_LENGTH_BONUS = 0.2
    LENGTH_THRESHOLD = 3


class HFModelConfig:
    """Configuration for Hugging Face transformer models."""

    DEFAULT_MODEL = "obi/deid_bert_i2b2"
    ROBERTA_MODEL = "obi/deid_roberta_i2b2"

    THRESHOLD_MAP: Dict[str, Dict[str, float]] = {
        "obi/deid_bert_i2b2": {
            "standard": 0.7,
            "high": 0.85,
            "very_high": 0.95,
            "recall_99.5": 4.656e-06,
            "recall_99.7": 1.898e-06
        },
        "obi/deid_roberta_i2b2": {
            "standard": 0.7,
            "high": 0.85,
            "very_high": 0.95,
            "recall_99.5": 2.436e-05,
            "recall_99.7": 2.396e-06
        }
    }


class EntityMappings:
    """Standard mappings between different entity type taxonomies."""

    PRESIDIO_TO_HIPAA: Dict[str, str] = {
        "PHONE_NUMBER": "PHONE_NUMBER",
        "US_PHONE_NUMBER": "PHONE_NUMBER",
        "FAX_NUMBER": "FAX_NUMBER",
        "EMAIL_ADDRESS": "EMAIL_ADDRESS",
        "US_SSN": "US_SSN",
        "SSN": "US_SSN",
        "URL": "URL",
        "IP_ADDRESS": "IP_ADDRESS",
        "US_DRIVER_LICENSE": "LICENSE_NUMBER",
        "US_PASSPORT": "LICENSE_NUMBER",
        "US_ITIN": "US_SSN",
        "CREDIT_CARD": "ACCOUNT_NUMBER",
        "IBAN_CODE": "ACCOUNT_NUMBER",
        "US_BANK_NUMBER": "ACCOUNT_NUMBER",
        "MEDICAL_LICENSE": "LICENSE_NUMBER",
        "NPI": "LICENSE_NUMBER",
        "DOMAIN_NAME": "URL",
        "LOCATION": "LOCATION",
        "GEOGRAPHIC_SUBDIVISION": "LOCATION",
        "GEOGRAPHY": "LOCATION",
        "PERSON": "NAME",
        "DATE_TIME": "DATE",
        "ORGANIZATION": "ORGANIZATION",
        "MRN": "MRN",
        "HEALTH_PLAN_ID": "HEALTH_PLAN_ID",
        "ACCOUNT_NUMBER": "ACCOUNT_NUMBER",
        "VEHICLE_ID": "VEHICLE_ID",
        "MEDICAL_DEVICE_ID": "DEVICE_ID",
        "DEVICE_ID": "DEVICE_ID",
        "BIOMETRIC_ID": "BIOMETRIC_ID",
        "PHOTO_ID": "PHOTO_ID",
    }

    SPACY_TO_HIPAA: Dict[str, str] = {
        "PERSON": "NAME",
        "GPE": "LOCATION",
        "LOC": "LOCATION",
        "FAC": "LOCATION",
        "GEOGRAPHIC_SUBDIVISION": "LOCATION",
        "ORG": "ORGANIZATION",
        "DATE": "DATE",
        "TIME": "DATE",
    }

    HF_TO_HIPAA: Dict[str, str] = {
        "PATIENT": "NAME",
        "STAFF": "NAME",
        "HOSP": "ORGANIZATION",
        "LOC": "LOCATION",
        "DATE": "DATE",
        "AGE": "AGE_OVER_89",
        "PHONE": "PHONE_NUMBER",
        "ID": "MRN",
        "PATORG": "ORGANIZATION",
        "EMAIL": "EMAIL_ADDRESS",
        "OTHERPHI": "UNKNOWN"
    }


class SupportedIdentifiers:
    """Entity types optimized for each detection method."""

    PRESIDIO: Set[str] = {
        "PHONE_NUMBER", "FAX_NUMBER", "EMAIL_ADDRESS", "US_SSN",
        "URL", "IP_ADDRESS", "LICENSE_NUMBER", "VEHICLE_ID",
        "DEVICE_ID", "NPI", "MRN",
        "NAME", "LOCATION", "ORGANIZATION", "DATE"
    }

    HUGGING_FACE: Set[str] = {
        "NAME", "ORGANIZATION", "LOCATION", "DATE",
        "AGE_OVER_89", "MRN"
    }

    SPACY: Set[str] = {
        "NAME", "LOCATION", "ORGANIZATION", "DATE"
    }


class HeaderExclusions:
    """Common document headers that should not be flagged as PHI."""

    COMMON_HEADERS = [
        "Outpatient Progress Note", "Discharge Summary", "After Visit Summary",
        "Emergency Department", "Triage Note", "Radiology Report", "Operative Note",
        "Home Health Nursing", "Patient Portal", "Referral Letter", "Chief Complaint",
        "History of Present Illness", "HPI", "Past Medical History", "PMH",
        "Medications", "Allergies", "Physical Exam", "Assessment", "Plan",
        "Follow-up", "Vitals", "Labs", "Impression", "Findings", "HIPAA", "Safe Harbor"
    ]
