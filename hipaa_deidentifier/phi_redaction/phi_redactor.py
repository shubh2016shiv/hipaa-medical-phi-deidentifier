"""
PHI Redaction Module

Implements various strategies for redacting or transforming detected PHI.
"""

import re
from typing import Dict, List, Optional

from ..models.phi_entity import PHIEntity
from ..utils.logger import get_logger
from ..utils.security import get_salt_from_config, PseudonymManager
from .redaction_config import RedactionConfig

logger = get_logger("redactor")


class PHIRedactor:
    """
    Applies redaction and transformation strategies to detected PHI.
    """

    def __init__(self, config: Dict):
        """
        Initializes the redactor with the specified configuration.

        Args:
            config: Configuration dictionary with redaction rules
        """
        self.config = config
        self.salt = get_salt_from_config(config)

        # Initialize specialized managers for consistent transformations
        self.pseudonym_manager = PseudonymManager(config)

        # Cache for clinical measurements to avoid redacting
        self.clinical_measurements_cache = {}

    def redact_text(
        self, text: str, entities: List[PHIEntity], patient_id: Optional[str] = None
    ) -> str:
        """
        Redacts or transforms PHI entities in the text.

        Args:
            text: The original text containing PHI
            entities: List of detected PHI entities
            patient_id: Optional patient identifier for consistent transformations

        Returns:
            The text with PHI redacted or transformed
        """
        # If no entities, return the original text
        if not entities:
            return text

        # Pre-process entities to handle special cases like email addresses
        processed_entities = []
        email_spans = set()

        # First pass: identify email addresses
        for entity in entities:
            # Expand EMAIL_ADDRESS entities to include the full whitespace-delimited
            # token in case the detector captured only a partial span.  Gated
            # strictly on category so that non-email entities whose text happens
            # to contain "@" (social handles, templated strings) are not
            # misclassified or have their boundaries silently altered.
            if entity.category == "EMAIL_ADDRESS":
                # Find the complete email address
                email_start = entity.start
                while email_start > 0 and text[email_start - 1] not in " \t\n\r":
                    email_start -= 1

                email_end = entity.end
                while email_end < len(text) and text[email_end] not in " \t\n\r":
                    email_end += 1

                # Mark this span as an email
                for i in range(email_start, email_end):
                    email_spans.add(i)

                # Create a new entity for the entire email
                processed_entities.append(
                    PHIEntity(
                        start=email_start,
                        end=email_end,
                        category="EMAIL_ADDRESS",
                        confidence=1.0,
                        text=text[email_start:email_end],
                    )
                )

        # Second pass: add all non-email entities
        for entity in entities:
            # Skip if this entity is part of an email
            is_email_part = False
            for i in range(entity.start, entity.end):
                if i in email_spans:
                    is_email_part = True
                    break

            if not is_email_part:
                processed_entities.append(entity)

        # Sort entities in reverse order (right to left)
        # This preserves the offsets as we make replacements
        sorted_entities = sorted(processed_entities, key=lambda e: e.end, reverse=True)

        # Make a copy of the text that we'll modify
        redacted_text = text

        # Track the spans we've already replaced to avoid overlapping replacements
        replaced_spans = []

        # Pre-process to identify clinical measurements that should not be redacted
        self._identify_clinical_measurements(text)

        # Apply transformations
        for entity in sorted_entities:
            # Check if this span overlaps with any already replaced span
            overlapping = False
            for start, end in replaced_spans:
                if max(entity.start, start) < min(entity.end, end):
                    overlapping = True
                    break

            # Skip if overlapping with already replaced span
            if overlapping:
                continue

            # Skip if this is a clinical measurement that should not be redacted.
            # The guard on PROTECTED_PHI_CATEGORIES ensures that entities the
            # detection pipeline has explicitly classified as PHI (NAME, MRN,
            # DATE, etc.) are never suppressed even if their extracted text
            # string coincidentally matches a cached vital/lab value — e.g. a
            # three-digit sodium reading ("142") colliding with an MRN fragment.
            if (
                entity.category not in RedactionConfig.PROTECTED_PHI_CATEGORIES
                and self._is_clinical_measurement(text[entity.start : entity.end])
            ):
                continue

            # Get the original text of the entity
            original_text = text[entity.start : entity.end]

            # Apply the appropriate transformation
            replacement = self._apply_transformation(
                entity.category, original_text, patient_id
            )

            # Replace the entity in the text
            redacted_text = (
                redacted_text[: entity.start]
                + replacement
                + redacted_text[entity.end :]
            )

            # Track this replaced span
            replaced_spans.append((entity.start, entity.end))

        return redacted_text

    def _apply_transformation(
        self, category: str, text: str, patient_id: Optional[str] = None
    ) -> str:
        """
        Applies the appropriate transformation to a PHI entity.

        Args:
            category: The category of PHI
            text: The text to transform
            patient_id: Optional patient identifier for consistent transformations

        Returns:
            The transformed text
        """
        # Get the rule for this category, or use the default
        rules = self.config.get("transform", {}).get("rules", {})
        rule = rules.get(
            category, self.config.get("transform", {}).get("default_action", "redact")
        )

        # Don't transform common section headers or clinical terms
        if self._is_common_header(text) or self._is_clinical_term(text):
            return text

        # Fix issue #2: Wrong PHI Categorization
        # These reclassifications correct specific structural mismatches between
        # what generic Presidio recognizers emit and what HIPAA categories the
        # redaction config actually handles.  The elif chain makes priority
        # explicit — the first match wins and no entity can be double-reclassified
        # by later branches.
        if category == "US_SSN" and re.match(r"\d{5}-\d{4}", text):
            # ZIP+4 codes (ddddd-dddd) are structurally indistinguishable from
            # SSNs to generic recognizers; the five-digit prefix is the discriminator.
            category = "ZIP"
            rule = rules.get("ZIP", rule)

        elif (
            "MRN" in text
            or re.match(r"[A-Z]+-[A-Z]+-\d+", text)
            or re.match(r"MRN-[A-Z]+-\d+-\d+", text)
            or re.match(r"MR-\d+-\d+", text)
        ):
            # MR-YYYY-NNNNNN is a subset of MR-\d+-\d+ so no separate branch needed.
            category = "MRN"
            rule = "hash"

        elif re.match(r"ENC-\d{4}-\d{2}-\d{2}-\d+", text):
            category = "ENCOUNTER_ID"
            rule = "redact"

        elif text.upper() in RedactionConfig.US_STATE_ABBR:
            # State abbreviations carry no generalizable form; redact directly.
            category = "LOCATION"
            rule = "redact"

        # Fix issue #5: Email & URL Corruption
        # Special handling for dates in format MM/DD/YYYY
        if category == "DATE" and re.match(r"\d{1,2}/\d{1,2}", text) and len(text) <= 5:
            # This is likely a partial date (MM/DD) without the year
            # Check if there's a year nearby in the original text
            return "[REDACTED:DATE]"

        # Special handling for email addresses - keep as one unit
        if category == "EMAIL_ADDRESS" or (category == "URL" and "@" in text):
            return "[REDACTED:EMAIL_ADDRESS]"

        # Special handling for URLs
        if category == "URL":
            return "[REDACTED:URL]"

        # Skip short text that's likely a false positive (e.g. a lone initial
        # "J" detected as NAME).  AGE and AGE_OVER_89 are exempt because
        # single or two-digit ages are legitimate short PHI.
        if len(
            text.strip()
        ) < RedactionConfig.MIN_TEXT_LENGTH_GENERAL and category not in [
            "AGE",
            "AGE_OVER_89",
        ]:
            logger.warning(
                "Suppressing short entity without redaction "
                "(category=%s, len=%d, text=%r) — verify this is not PHI",
                category,
                len(text.strip()),
                text,
            )
            return text

        # Apply the appropriate transformation
        if rule == "redact":
            return f"[REDACTED:{category}]"

        elif rule in ("hash", "pseudonym"):
            # Both rules delegate to the pseudonym manager which produces a
            # deterministic HMAC-SHA256 code — the config key distinction is
            # cosmetic and carries no behavioural difference today.
            if len(text.strip()) < RedactionConfig.MIN_TEXT_LENGTH_FOR_HASH:
                return f"[REDACTED:{category}]"
            return self.pseudonym_manager.get_pseudonym(text, category, patient_id)

        elif rule == "generalize":
            if category == "ZIP":
                # Keep only first digits of ZIP code per HIPAA safe harbor
                zip_match = re.match(r"(\d{5})-?\d{0,4}", text)
                if zip_match:
                    return f"{zip_match.group(1)[: RedactionConfig.ZIP_GENERALIZED_LENGTH]}{RedactionConfig.ZIP_PLACEHOLDER}"
                return self.pseudonym_manager.get_pseudonym(text, "ZIP", patient_id)
            elif category == "AGE_OVER_89":
                return "AGE_OVER_89"
            else:
                return f"[GENERALIZED:{category}]"

        elif rule == "date_shift":
            # For US healthcare data, always redact dates completely for maximum HIPAA compliance
            # This is safer than date shifting which could potentially reveal patterns
            return "[REDACTED:DATE]"

        # Default fallback
        return f"[REDACTED:{category}]"

    def _is_common_header(self, text: str) -> bool:
        """
        Check if text is a common header that should not be redacted.

        Args:
            text: Text to check

        Returns:
            True if the text is a common header
        """
        # Check exact match
        if (
            text in RedactionConfig.COMMON_HEADERS
            or text.strip() in RedactionConfig.COMMON_HEADERS
        ):
            return True

        for phrase in RedactionConfig.HEADER_PHRASES:
            if phrase in text:
                return True

        # Check if this is a section header (common format in medical notes)
        section_header_pattern = r"^[A-Z][a-zA-Z\s/]+:$"
        if re.match(section_header_pattern, text.strip()):
            return True

        return False

    def _is_clinical_term(self, text: str) -> bool:
        """
        Check if text is a clinical term that should not be redacted.

        Args:
            text: Text to check

        Returns:
            True if the text is a clinical term
        """
        # Check if text is a clinical term
        if (
            text in RedactionConfig.CLINICAL_TERMS
            or text.strip() in RedactionConfig.CLINICAL_TERMS
        ):
            return True

        # Check if text is a medication dose (e.g., "0.25 mg")
        if re.search(r"\d+\.?\d*\s*mg", text.strip()):
            return True

        for phrase in RedactionConfig.CLINICAL_PHRASES:
            if phrase in text:
                return True

        return False

    def _identify_clinical_measurements(self, text: str) -> None:
        """
        Identify clinical measurements in the text that should not be redacted.

        Args:
            text: The text to analyze
        """
        for pattern in RedactionConfig.VITAL_PATTERNS + RedactionConfig.LAB_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                full_match = match.group(0)
                value_match = match.group(1)

                # Cache both the full match and the value
                self.clinical_measurements_cache[full_match] = True
                self.clinical_measurements_cache[value_match] = True

    def _is_clinical_measurement(self, text: str) -> bool:
        """
        Check if text represents a clinical measurement that should not be redacted.

        Args:
            text: Text to check

        Returns:
            True if the text is a clinical measurement, False otherwise
        """
        return text in self.clinical_measurements_cache
