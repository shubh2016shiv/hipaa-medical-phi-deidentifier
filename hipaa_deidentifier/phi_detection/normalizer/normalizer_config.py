#!/usr/bin/env python3
"""
Normalizer Configuration Constants

Centralizes all configuration constants for text normalization.
Eliminates magic numbers and provides clear documentation.

Enterprise Best Practice: Configuration as Code
"""

from typing import Dict


# =============================================================================
# Character Mappings
# =============================================================================


class CharacterMappings:
    """Unicode and OCR confusable character mappings."""

    # Unicode confusable characters (quotation marks, dashes, spaces)
    UNICODE_CONFUSABLES: Dict[str, str] = {
        "\u2018": "'",  # Left single quotation mark
        "\u2019": "'",  # Right single quotation mark
        "\u201c": '"',  # Left double quotation mark
        "\u201d": '"',  # Right double quotation mark
        "\u2013": "-",  # En dash
        "\u2014": "-",  # Em dash
        "\u2212": "-",  # Minus sign
        "\u00a0": " ",  # Non-breaking space
    }

    # Zero-width and control characters to skip
    ZERO_WIDTH_CHARS = ["\u200b", "\u200c", "\u200d"]

    # Unicode categories to filter (control, format, surrogate)
    CONTROL_CATEGORIES = ["Cc", "Cf", "Cs"]


# =============================================================================
# OCR Error Patterns
# =============================================================================


class OCRPatterns:
    """Common OCR errors and their corrections."""

    # Common OCR confusable characters
    # Note: These should be applied contextually, not globally
    OCR_CONFUSABLES: Dict[str, str] = {
        "0": "O",  # Zero to letter O (in context)
        "l": "I",  # Lowercase L to uppercase I (in context)
        "1": "l",  # One to lowercase L (in context)
        "I": "1",  # Uppercase I to one (in context)
    }

    # Known header tokens that might have OCR errors
    HEADER_TOKENS = {
        "DOB",  # Date of Birth
        "D0B",  # OCR error: DOB with zero
        "MRN",  # Medical Record Number
        "ACC",  # Account
        "ACCOUNT",
        "HICN",  # Health Insurance Claim Number
        "PLAN",
        "ID",
        "SSN",  # Social Security Number
        "PATIENT",
        "DEVICE",
        "SN",  # Serial Number
    }

    # OCR date pattern corrections (regex patterns)
    DATE_PATTERNS = [
        (r"\b0l/(\d+)/(\d{4})\b", r"01/\1/\2"),  # 0l/15/1980 -> 01/15/1980
        (r"\b(\d+)/0l/(\d{4})\b", r"\1/01/\2"),  # 15/0l/1980 -> 15/01/1980
        (r"\b0l/0l/(\d{4})\b", r"01/01/\1"),  # 0l/0l/1980 -> 01/01/1980
    ]


# =============================================================================
# Regex Patterns
# =============================================================================


class NormalizationPatterns:
    """Regex patterns for text normalization."""

    # URL pattern (http/https)
    URL_PATTERN = r"https?://\S+"

    # Filename pattern (common document extensions)
    FILENAME_PATTERN = r"\b[\w.-]+\.(pdf|png|jpg|jpeg|tif|tiff|txt|rtf|docx)\b"

    # Multiple spaces (3 or more)
    MULTIPLE_SPACES = r"[ \t]{3,}"

    # Padded separators (spaces around . - /)
    PADDED_SEPARATOR = r"\s*([.\-/])\s*"

    # Hyphenated word wrap (word-<space>word)
    WRAP_HYPHEN = r"([A-Za-z])-\s+([A-Za-z])"

    # Word boundary (for tokenization)
    WORD_BOUNDARY = r"\b\w+\b"


# =============================================================================
# Normalization Settings
# =============================================================================


class NormalizationSettings:
    """Settings for normalization behavior."""

    # Maximum iterations for de-hyphenation (prevent infinite loops)
    MAX_DEHYPHENATION_ITERATIONS = 2

    # Token length constraints for OCR header detection
    MIN_HEADER_TOKEN_LENGTH = 2
    MAX_HEADER_TOKEN_LENGTH = 10

    # Unicode normalization form (NFKC: Compatibility Decomposition + Canonical Composition)
    UNICODE_FORM = "NFKC"

    # Characters to preserve during control character filtering
    PRESERVED_CONTROL_CHARS = {"\n", "\t"}
