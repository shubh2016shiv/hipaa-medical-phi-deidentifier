#!/usr/bin/env python3
"""
Redaction Configuration Constants

Centralizes all configuration constants for PHI redaction.
Eliminates magic numbers and provides clear documentation.

Enterprise Best Practice: Configuration as Code
"""

from typing import List, Set


class RedactionConfig:
    """Configuration constants for PHI redaction."""

    # Minimum text length to avoid false positives
    MIN_TEXT_LENGTH_FOR_HASH = 4
    MIN_TEXT_LENGTH_FOR_PSEUDONYM = 4
    MIN_TEXT_LENGTH_GENERAL = 3

    # ZIP code generalization
    ZIP_GENERALIZED_LENGTH = 3
    ZIP_PLACEHOLDER = "XX"

    # Default transformation actions
    DEFAULT_ACTION = "redact"

    # US State abbreviations
    US_STATE_ABBR: Set[str] = {
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
        "DC",
        "PR",
        "VI",
        "GU",
        "AS",
        "MP",
    }

    # Common medical document headers (should not be redacted)
    COMMON_HEADERS: Set[str] = {
        "Outpatient Progress Note",
        "Discharge Summary",
        "After Visit Summary",
        "Emergency Department",
        "Triage Note",
        "Radiology Report",
        "Operative Note",
        "Home Health Nursing",
        "Patient Portal",
        "Referral Letter",
        "Chief Complaint",
        "History of Present Illness",
        "HPI",
        "Past Medical History",
        "PMH",
        "Medications",
        "Allergies",
        "Physical Exam",
        "Assessment",
        "Plan",
        "Follow-up",
        "Vitals",
        "Labs",
        "Impression",
        "Findings",
        "HIPAA",
        "Safe Harbor",
        "Identifiers Test",
        "Assessment/Plan",
    }

    # Header phrases that identify document section headers (should not be redacted).
    # IMPORTANT: never add healthcare facility keywords here (e.g. "Hospital",
    # "Clinic", "Medical Center").  FacilityLocationRecognizer uses those exact
    # strings as detection signals, so listing them here would silently block
    # redaction of every facility-name entity that passes the FP Guardrail.
    HEADER_PHRASES: List[str] = [
        "Progress Note",
        "Visit Summary",
        "Discharge Summary",
        "Triage Note",
        "Radiology Report",
        "Operative Note",
        "Referral Letter",
        "HIPAA Safe Harbor",
        "Chief Complaint",
        "Assessment/Plan",
        "Follow-up",
    ]

    # PHI categories that must never be suppressed by clinical-measurement
    # heuristics.  Any entity whose category is in this set is redacted
    # regardless of whether its extracted text string resembles a vital sign
    # or lab value — the detection pipeline already confirmed it is PHI.
    PROTECTED_PHI_CATEGORIES: frozenset = frozenset(
        {
            "NAME",
            "DATE",
            "LOCATION",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "FAX_NUMBER",
            "US_SSN",
            "MRN",
            "ENCOUNTER_ID",
            "ACCOUNT_NUMBER",
            "HEALTH_PLAN_ID",
            "LICENSE_NUMBER",
            "VEHICLE_ID",
            "DEVICE_ID",
            "URL",
            "IP_ADDRESS",
            "BIOMETRIC_ID",
            "PHOTO_ID",
            "AGE",
            "AGE_OVER_89",
            "OTHER_ID",
            "ORGANIZATION",
        }
    )

    # Clinical terms (medical abbreviations and terms)
    CLINICAL_TERMS: Set[str] = {
        "NSTEMI",
        "STEMI",
        "T2DM",
        "HTN",
        "CABG",
        "GLP-1",
        "RA",
        "mg",
        "BID",
        "TID",
        "QID",
        "PRN",
        "PO",
        "IV",
        "IM",
        "SC",
        "SQ",
        "weekly",
        "daily",
        "morning",
        "dizziness",
        "Occasional",
        "denies",
        "reports",
        "states",
        "endorses",
        "tolerating",
        "ambulating",
        "verbalized",
    }

    # Clinical phrases that should be preserved
    CLINICAL_PHRASES: List[str] = [
        "morning dizziness",
        "mg once weekly",
        "mg daily",
        "mg BID",
        "mg TID",
        "mg QID",
        "verbalized understanding",
        "patient education",
        "discharge instructions",
        "informed consent",
    ]

    # Regex patterns for vitals and lab values
    VITAL_PATTERNS: List[str] = [
        r"\bBP\s+(\d{2,3}/\d{2,3})\b",  # Blood pressure
        r"\bHR\s+(\d{2,3})\b",  # Heart rate
        r"\bRR\s+(\d{1,2})\b",  # Respiratory rate
        r"\bT\s+(\d{2}\.\d)\b",  # Temperature
        r"\bTemp\s+(\d{2}\.\d)\b",  # Temperature
        r"\bO2\s+(\d{1,3}%)\b",  # Oxygen saturation
        r"\bSPO2\s+(\d{1,3}%)\b",  # Oxygen saturation
        r"\bWT\s+(\d{1,3}\.\d)\b",  # Weight
        r"\bHT\s+(\d{1,3})\b",  # Height
        r"\bBMI\s+(\d{1,2}\.\d)\b",  # BMI
    ]

    LAB_PATTERNS: List[str] = [
        r"\bA1c\s+(\d{1,2}\.\d%)\b",  # Hemoglobin A1c
        r"\bHbA1c\s+(\d{1,2}\.\d%)\b",  # Hemoglobin A1c
        r"\bLDL\s+(\d{1,3})\b",  # LDL cholesterol
        r"\bHDL\s+(\d{1,3})\b",  # HDL cholesterol
        r"\bTSH\s+(\d{1,2}\.\d{1,3})\b",  # Thyroid stimulating hormone
        r"\bWBC\s+(\d{1,2}\.\d)\b",  # White blood cell count
        r"\bHGB\s+(\d{1,2}\.\d)\b",  # Hemoglobin
        r"\bHCT\s+(\d{1,2}\.\d)\b",  # Hematocrit
        r"\bPLT\s+(\d{1,3})\b",  # Platelet count
        r"\bCR\s+(\d{1,2}\.\d{1,2})\b",  # Creatinine
        r"\bBUN\s+(\d{1,2})\b",  # Blood urea nitrogen
        r"\bNA\s+(\d{3})\b",  # Sodium
        r"\bK\s+(\d{1,2}\.\d)\b",  # Potassium
        r"\bGLU\s+(\d{1,3})\b",  # Glucose
    ]
