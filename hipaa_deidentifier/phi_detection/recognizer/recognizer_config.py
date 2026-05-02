#!/usr/bin/env python3
"""
Recognizer Configuration Constants

Centralizes all configuration constants, patterns, and thresholds for PHI recognizers.
Eliminates magic numbers and provides clear documentation for all detection rules.

Enterprise Best Practice: Configuration as Code
"""

from typing import Set


class RecognizerThresholds:
    """Confidence score thresholds for PHI recognition."""

    # High confidence thresholds
    VERY_HIGH_CONFIDENCE = 0.95
    HIGH_CONFIDENCE = 0.9
    MEDIUM_HIGH_CONFIDENCE = 0.85
    MEDIUM_CONFIDENCE = 0.8

    # Lower confidence thresholds (require additional validation)
    MEDIUM_LOW_CONFIDENCE = 0.75
    LOW_CONFIDENCE = 0.7
    VERY_LOW_CONFIDENCE = 0.65
    MINIMUM_CONFIDENCE = 0.5


class SSNConfig:
    """Configuration for Social Security Number recognition."""

    # Invalid SSN prefixes and patterns
    INVALID_AREA_NUMBERS = {"000", "666"}
    INVALID_GROUP_NUMBER = "00"
    INVALID_SERIAL_NUMBER = "0000"

    # SSN must be exactly 9 digits
    SSN_LENGTH = 9

    # Area numbers starting with 9 are invalid
    @staticmethod
    def is_invalid_area_prefix(area: str) -> bool:
        """Check if area number has invalid prefix."""
        return area.startswith("9")


class MRNConfig:
    """Configuration for Medical Record Number recognition."""

    # MRN length constraints
    MIN_MRN_LENGTH = 6
    MAX_MRN_LENGTH = 18
    MIN_NUMERIC_MRN_LENGTH = 8
    MAX_NUMERIC_MRN_LENGTH = 10

    # Context keywords that indicate MRN
    CONTEXT_KEYWORDS = {
        "patient",
        "record",
        "chart",
        "account",
        "medical",
        "mrn",
        "admission",
        "visit",
    }


class DateConfig:
    """Configuration for date recognition."""

    # Minimum year for valid dates (to avoid false positives)
    MIN_YEAR = 1900
    MAX_YEAR = 2100

    # Month abbreviations
    MONTH_ABBR = {
        "jan",
        "feb",
        "mar",
        "apr",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
    }

    # Date-related context keywords
    DATE_CONTEXT_KEYWORDS = {
        "dob",
        "birth",
        "born",
        "date",
        "admission",
        "discharge",
        "visit",
        "appointment",
    }


class LocationConfig:
    """Configuration for US location recognition."""

    # US State abbreviations (all 50 states + DC + territories)
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

    # ZIP code lengths
    ZIP_5_LENGTH = 5
    ZIP_9_LENGTH = 9  # ZIP+4 format

    # Street type abbreviations
    STREET_TYPES = {
        "street",
        "st",
        "avenue",
        "ave",
        "road",
        "rd",
        "drive",
        "dr",
        "boulevard",
        "blvd",
        "lane",
        "ln",
        "place",
        "pl",
        "court",
        "ct",
        "circle",
        "cir",
        "way",
        "parkway",
        "pkwy",
        "highway",
        "hwy",
    }


class PhoneConfig:
    """Configuration for phone/fax number recognition."""

    # US phone number format
    AREA_CODE_LENGTH = 3
    EXCHANGE_LENGTH = 3
    NUMBER_LENGTH = 4
    TOTAL_PHONE_LENGTH = 10  # Without country code

    # Context keywords for fax identification
    FAX_KEYWORDS = {"fax", "facsimile", "telefax"}

    # Context keywords for phone identification
    PHONE_KEYWORDS = {"phone", "tel", "telephone", "cell", "mobile", "contact"}


class IdentifierConfig:
    """Configuration for various identifier types."""

    # Health plan ID
    HEALTH_PLAN_MIN_LENGTH = 6
    HEALTH_PLAN_MAX_LENGTH = 20
    COMMON_INSURERS = {"bcbs", "uhc", "aetna", "cigna", "humana", "anthem"}

    # Account numbers
    ACCOUNT_MIN_LENGTH = 6
    ACCOUNT_MAX_LENGTH = 20

    # Device IDs
    DEVICE_MIN_LENGTH = 3
    DEVICE_MAX_LENGTH = 20

    # Vehicle IDs
    VIN_LENGTH = 17
    LICENSE_PLATE_MIN_LENGTH = 5
    LICENSE_PLATE_MAX_LENGTH = 10

    # Photo/Image IDs
    PHOTO_ID_MIN_LENGTH = 3
    PHOTO_ID_MAX_LENGTH = 30
    SUPPORTED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "tiff"}

    # Biometric IDs
    BIOMETRIC_MIN_LENGTH = 3
    BIOMETRIC_MAX_LENGTH = 20


class AgeConfig:
    """Configuration for age-related detection."""

    # HIPAA Safe Harbor threshold
    AGE_THRESHOLD = 89

    # Age range for validation
    MIN_AGE = 0
    MAX_AGE = 120

    # Birth year calculation (years that indicate age > 89)
    CURRENT_YEAR = 2025  # Update annually or calculate dynamically

    @staticmethod
    def calculate_age_from_birth_year(birth_year: int) -> int:
        """Calculate age from birth year."""
        return AgeConfig.CURRENT_YEAR - birth_year

    @staticmethod
    def is_over_threshold(age: int) -> bool:
        """Check if age exceeds HIPAA threshold."""
        return age > AgeConfig.AGE_THRESHOLD


class EncounterConfig:
    """Configuration for encounter/visit ID recognition."""

    # Encounter ID length constraints
    MIN_ENCOUNTER_LENGTH = 6
    MAX_ENCOUNTER_LENGTH = 18

    # Common encounter ID prefixes
    ENCOUNTER_PREFIXES = {"enc", "vst", "adm", "visit", "encounter", "admission"}

    # Context keywords
    ENCOUNTER_KEYWORDS = {
        "encounter",
        "visit",
        "admission",
        "admitted",
        "hospitalization",
        "inpatient",
        "outpatient",
        "ed",
        "er",
        "emergency",
    }


class RecognizerPatterns:
    """Common regex patterns used across recognizers."""

    # Word boundary patterns
    WORD_BOUNDARY_START = r"\b"
    WORD_BOUNDARY_END = r"\b"

    # Separator patterns
    DASH_SEPARATOR = r"[-]?"
    SPACE_SEPARATOR = r"\s*"
    COLON_SEPARATOR = r"[:#=\-]?"

    # Numeric patterns
    DIGIT = r"\d"
    ALPHA = r"[A-Z]"
    ALPHANUM = r"[A-Z0-9]"

    # Phone number pattern components
    US_PHONE_PATTERN = r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    US_PHONE_WITH_COUNTRY_CODE = (
        r"(?:\+?1\s*[-\.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    )

    # Date pattern components
    MONTH_DAY_YEAR = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    YEAR_MONTH_DAY = r"\d{4}[/-]\d{1,2}[/-]\d{1,2}"

    # Common label patterns
    LABEL_COLON = r"\s*[:#=\-]?\s*"
    LABEL_HASH = r"\s*[#]?\s*"
