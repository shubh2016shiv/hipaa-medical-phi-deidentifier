#!/usr/bin/env python3
"""
Presidio-based De-identifier Module

This module specializes in detecting structured PHI entities using Microsoft Presidio.
It focuses on identifiers with clear patterns like phone numbers, emails, SSNs, etc.
"""

import re
from typing import Dict, List, Optional, Set

from presidio_analyzer import AnalyzerEngine

from hipaa_deidentifier.models.phi_entity import PHIEntity
from hipaa_deidentifier.phi_detection.recognizer.custom_recognizers import MedicalRecordNumberRecognizer, EncounterIdentifierRecognizer, AgeOver89Recognizer
from hipaa_deidentifier.phi_detection.recognizer.hipaa_recognizers import HealthPlanIDRecognizer, VehicleIDRecognizer, BiometricIDRecognizer
from hipaa_deidentifier.phi_detection.recognizer.account_number_recognizer import AccountNumberRecognizer
from hipaa_deidentifier.phi_detection.recognizer.device_id_recognizer import DeviceIDRecognizer
from hipaa_deidentifier.phi_detection.recognizer.photo_id_recognizer import PhotoIDRecognizer
from hipaa_deidentifier.phi_detection.recognizer.fax_recognizer import EnhancedFaxRecognizer
from hipaa_deidentifier.phi_detection.recognizer.custom_ssn_recognizer import CustomSSNRecognizer
from hipaa_deidentifier.phi_detection.recognizer.custom_date_recognizer import CustomDateRecognizer
from hipaa_deidentifier.phi_detection.recognizer.mrn_recognizer import EnhancedMRNRecognizer
from hipaa_deidentifier.phi_detection.recognizer.us_location_recognizer import USLocationRecognizer
from config.config import config as global_config
from hipaa_deidentifier.phi_detection.clinical_patterns import detect_initials_and_nicknames, detect_facility_names, detect_relatives_and_contacts
from hipaa_deidentifier.phi_detection.normalizer.phi_normalizer import Stage0Normalizer


class PresidioDeidentifier:
    """
    Specialized de-identifier that uses Microsoft Presidio for structured PHI detection.
    
    This class focuses on detecting PHI entities with clear patterns:
    - Phone numbers
    - Fax numbers
    - Email addresses
    - Social Security Numbers (SSNs)
    - URLs
    - IP addresses
    - License numbers
    - Vehicle identifiers (VINs)
    - Medical device identifiers
    """
    
    # Map Presidio entity types to our PHI categories
    PRESIDIO_MAPPING = {
        "PHONE_NUMBER": "PHONE_NUMBER",
        "US_PHONE_NUMBER": "PHONE_NUMBER",
        "FAX_NUMBER": "FAX_NUMBER",
        "EMAIL_ADDRESS": "EMAIL_ADDRESS",
        "US_SSN": "US_SSN",
        "SSN": "US_SSN",  # Map SSN to US_SSN for consistency
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
        "GEOGRAPHIC_SUBDIVISION": "LOCATION",  # Map Presidio's geographic subdivision to LOCATION
        "GEOGRAPHY": "LOCATION",  # Map Presidio's GEOGRAPHY to LOCATION
        "PERSON": "NAME",
        "DATE_TIME": "DATE",
        "ORGANIZATION": "ORGANIZATION",
        "MRN": "MRN",  # Add MRN mapping
        "HEALTH_PLAN_ID": "HEALTH_PLAN_ID",
        "ACCOUNT_NUMBER": "ACCOUNT_NUMBER",
        "VEHICLE_ID": "VEHICLE_ID",
        "MEDICAL_DEVICE_ID": "DEVICE_ID",
        "DEVICE_ID": "DEVICE_ID",
        "BIOMETRIC_ID": "BIOMETRIC_ID",
        "PHOTO_ID": "PHOTO_ID",
        # OTHER_ID removed as per user request
        "SSN": "US_SSN"  # Map SSN to US_SSN for consistency
    }
    
    # Identifiers that Presidio is best suited for (now includes spaCy entities)
    PRESIDIO_OPTIMIZED_IDENTIFIERS = {
        # Structured PHI (Presidio's strength)
        "PHONE_NUMBER", "FAX_NUMBER", "EMAIL_ADDRESS", "US_SSN", 
        "URL", "IP_ADDRESS", "LICENSE_NUMBER", "VEHICLE_ID", 
        "MEDICAL_DEVICE_ID", "MRN",
        # General entities (spaCy's strength - now integrated)
        "NAME", "LOCATION", "ORGANIZATION", "DATE"
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the Presidio-based de-identifier.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Initialize Presidio analyzer engine
        self.analyzer = self._create_analyzer_engine()
        
        # Initialize the text normalizer (Stage 0)
        self.text_normalizer = Stage0Normalizer()
        
        # Get targeted identifiers from config or use default
        # Check in detect.presidio_identifiers first, then fall back to root presidio_identifiers
        detect_config = self.config.get("detect", {})
        self.target_identifiers = detect_config.get("presidio_identifiers", 
                                                  self.config.get("presidio_identifiers", 
                                                                self.PRESIDIO_OPTIMIZED_IDENTIFIERS))
        
        # Get detection threshold from config
        detection_thresholds = self.config.get("detection_thresholds", {})
        if isinstance(detection_thresholds, dict):
            self.threshold = detection_thresholds.get("presidio", 0.5)
        else:
            self.threshold = 0.5
    
    def _create_analyzer_engine(self) -> AnalyzerEngine:
        """
        Create and configure the Presidio analyzer engine.
        
        Returns:
            Configured Presidio analyzer engine
        """
        # Get analyzer from centralized config
        analyzer = global_config.get_analyzer()
        
        # Get the registry and add custom healthcare recognizers
        registry = analyzer.registry
        
        # Add basic medical recognizers
        # Add enhanced MRN recognizer first (higher priority)
        registry.add_recognizer(EnhancedMRNRecognizer())
        
        registry.add_recognizer(MedicalRecordNumberRecognizer())
        registry.add_recognizer(EncounterIdentifierRecognizer())
        registry.add_recognizer(AgeOver89Recognizer())
        
        # Add custom SSN recognizer (replace Presidio's default)
        registry.add_recognizer(CustomSSNRecognizer())
        
        # Add custom date recognizer (replace Presidio's default)
        registry.add_recognizer(CustomDateRecognizer())
        
        # Add HIPAA-specific recognizers for all 18 identifiers
        # Add HIPAA-specific recognizers for all identifiers
        registry.add_recognizer(HealthPlanIDRecognizer())
        registry.add_recognizer(VehicleIDRecognizer())
        registry.add_recognizer(BiometricIDRecognizer())
        registry.add_recognizer(PhotoIDRecognizer())
        registry.add_recognizer(AccountNumberRecognizer())
        registry.add_recognizer(DeviceIDRecognizer())
        registry.add_recognizer(EnhancedFaxRecognizer())
        # Add US-specific location recognizer
        registry.add_recognizer(USLocationRecognizer())
        # OtherIDRecognizer removed as per user request
        
        # Add custom phone number recognizer with higher confidence
        from presidio_analyzer import Pattern, PatternRecognizer
        phone_patterns = [
            # Phone numbers with explicit phone labels
            Pattern(
                name="us_phone_labeled",
                regex=r"\b(?:Phone|Tel|Telephone|Call|Mobile|Cell)\s*[:#=\-]?\s*(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b",
                score=0.95
            ),
            # Standalone phone numbers
            Pattern(
                name="us_phone_standalone_paren",
                regex=r"\(\d{3}\)\s*\d{3}-\d{4}",
                score=0.9
            ),
            Pattern(
                name="us_phone_standalone_dash",
                regex=r"\d{3}-\d{3}-\d{4}",
                score=0.9
            ),
            Pattern(
                name="us_phone_standalone_dot",
                regex=r"\d{3}\.\d{3}\.\d{4}",
                score=0.9
            ),
            Pattern(
                name="us_phone_standalone_space",
                regex=r"\d{3}\s+\d{3}\s+\d{4}",
                score=0.85
            )
        ]
        phone_recognizer = PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            patterns=phone_patterns
        )
        registry.add_recognizer(phone_recognizer)
        
        return analyzer
    
    def detect(self, text: str) -> List[PHIEntity]:
        """
        Detect structured PHI entities in the text using Presidio.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected PHI entities
        """
        # Stage 0: Normalize text while maintaining character mapping
        stage0_result = self.text_normalizer.stage0_normalize_and_candidates(text)
        normalized_text = stage0_result["normalized_text"]
        project_fn = stage0_result["project_fn"]
        
        # Convert our identifier categories to Presidio entity types
        presidio_entity_types = self._map_to_presidio_types(self.target_identifiers)
        
        # Run Presidio analyzer on normalized text
        results = self.analyzer.analyze(
            text=normalized_text,
            entities=presidio_entity_types,
            language="en",
            score_threshold=self.threshold
        )
        
        # Convert Presidio results to PHI entities
        entities = []
        for result in results:
            # Map Presidio entity type to our category
            category = self.PRESIDIO_MAPPING.get(result.entity_type, "UNKNOWN")
            
            # Project span back to original text
            original_start, original_end = project_fn(result.start, result.end)
            
            # Create PHI entity
            entity = PHIEntity(
                start=original_start,
                end=original_end,
                category=category,
                confidence=result.score,
                text=text[original_start:original_end]
            )
            # Set source for tracking
            entity.source = "presidio"
            entities.append(entity)
        
        # Note: spaCy detection is already integrated into Presidio's built-in recognizers
        # No need for separate spaCy detection since Presidio uses the large spaCy model internally
        
        # Add clinical pattern detection
        clinical_entities = self._detect_clinical_patterns(text)
        entities.extend(clinical_entities)
        
        # Add FAX number detection in post-processing to avoid overlap
        fax_entities = self._detect_fax_numbers(text)
        
        # Remove overlapping phone numbers that are actually fax numbers
        entities = self._remove_overlapping_phone_fax(entities, fax_entities)
        
        # Add fax entities
        entities.extend(fax_entities)
        
        return entities
    
    def _detect_fax_numbers(self, text: str) -> List[PHIEntity]:
        """
        Detect FAX numbers with explicit fax labels.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected FAX entities
        """
        # Stage 0: Normalize text while maintaining character mapping
        stage0_result = self.text_normalizer.stage0_normalize_and_candidates(text)
        normalized_text = stage0_result["normalized_text"]
        project_fn = stage0_result["project_fn"]
        
        entities = []
        
        # FAX number patterns with explicit labels
        fax_patterns = [
            r"\b(?:Fax|FAX|Facsimile)\s*[:#=\-]?\s*(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b",
            r"\b(?:Fax|FAX)\s*[:#=\-]?\s*(\(\d{3}\)\s*\d{3}[-.\s]?\d{4})\b",
            r"\b(?:Fax|FAX)\s*[:#=\-]?\s*(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})\b"
        ]
        
        for pattern in fax_patterns:
            for match in re.finditer(pattern, normalized_text):
                # Get the phone number part (group 1)
                phone_number = match.group(1)
                start, end = match.span(1)
                
                # Project span back to original text
                original_start, original_end = project_fn(start, end)
                
                # Create FAX entity
                entity = PHIEntity(
                    start=original_start,
                    end=original_end,
                    category="FAX_NUMBER",
                    confidence=0.95,
                    text=text[original_start:original_end]
                )
                entities.append(entity)
        
        return entities
    
    def _remove_overlapping_phone_fax(self, phone_entities: List[PHIEntity], fax_entities: List[PHIEntity]) -> List[PHIEntity]:
        """
        Remove phone number entities that overlap with fax number entities.
        
        Args:
            phone_entities: List of phone number entities
            fax_entities: List of fax number entities
            
        Returns:
            Filtered list of phone entities without overlaps
        """
        if not fax_entities:
            return phone_entities
        
        # Create a set of fax entity positions for quick lookup
        fax_positions = set()
        for fax_entity in fax_entities:
            for pos in range(fax_entity.start, fax_entity.end):
                fax_positions.add(pos)
        
        # Filter out phone entities that overlap with fax entities
        filtered_entities = []
        for phone_entity in phone_entities:
            # Check if any position of the phone entity overlaps with fax positions
            phone_positions = set(range(phone_entity.start, phone_entity.end))
            if not phone_positions.intersection(fax_positions):
                filtered_entities.append(phone_entity)
        
        return filtered_entities
    
    def detect_with_header_patterns(self, text: str) -> List[PHIEntity]:
        """
        Detect PHI entities in header patterns.
        
        This reuses the sophisticated header pattern detection from pattern_detector.py
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected PHI entities
        """
        # Stage 0: Normalize text while maintaining character mapping
        stage0_result = self.text_normalizer.stage0_normalize_and_candidates(text)
        normalized_text = stage0_result["normalized_text"]
        project_fn = stage0_result["project_fn"]
        
        entities = []
        
        # Patient name in header
        for match in re.finditer(r"(?i)\bPatient\s*(?:Name)?\s*:\s*([A-Z][a-zA-Z\-\s']{1,60})", normalized_text):
            start, end = match.span(1)
            confidence = 0.85
            if confidence >= self.threshold:  # Apply threshold filtering
                # Project span back to original text
                original_start, original_end = project_fn(start, end)
                entities.append(PHIEntity(
                    start=original_start,
                    end=original_end,
                    category="NAME",
                    confidence=confidence,
                    text=text[original_start:original_end],
                ))
        
        # Doctor name in header
        for match in re.finditer(r"(?i)\b(?:Doctor|Dr|Physician|Provider)\s*(?:Name)?\s*:\s*([A-Z][a-zA-Z\-\s']{1,60})", normalized_text):
            start, end = match.span(1)
            confidence = 0.85
            if confidence >= self.threshold:  # Apply threshold filtering
                # Project span back to original text
                original_start, original_end = project_fn(start, end)
                entities.append(PHIEntity(
                    start=original_start,
                    end=original_end,
                    category="NAME",
                    confidence=confidence,
                    text=text[original_start:original_end],
                ))
        
        # Skip common section headers
        common_headers = [
            "Outpatient Progress Note", "Discharge Summary", "After Visit Summary",
            "Emergency Department", "Triage Note", "Radiology Report", "Operative Note",
            "Home Health Nursing", "Patient Portal", "Referral Letter", "Chief Complaint",
            "History of Present Illness", "HPI", "Past Medical History", "PMH",
            "Medications", "Allergies", "Physical Exam", "Assessment", "Plan",
            "Follow-up", "Vitals", "Labs", "Impression", "Findings", "HIPAA", "Safe Harbor"
        ]
        
        # Remove entities that match common headers
        filtered_entities = []
        for entity in entities:
            entity_text = text[entity.start:entity.end]
            if entity_text not in common_headers and entity_text.strip() not in common_headers:
                filtered_entities.append(entity)
                
        return filtered_entities
    
    def _map_to_presidio_types(self, our_identifiers: Set[str]) -> List[str]:
        """
        Map our identifier categories to Presidio entity types.
        
        Args:
            our_identifiers: Set of our identifier categories
            
        Returns:
            List of corresponding Presidio entity types
        """
        # Create reverse mapping (our category -> Presidio entity type)
        reverse_mapping = {}
        for presidio_type, our_category in self.PRESIDIO_MAPPING.items():
            if our_category not in reverse_mapping:
                reverse_mapping[our_category] = []
            reverse_mapping[our_category].append(presidio_type)
        
        # Map our identifiers to Presidio entity types
        presidio_types = []
        for identifier in our_identifiers:
            if identifier in reverse_mapping:
                presidio_types.extend(reverse_mapping[identifier])
        
        return presidio_types
    
    def _detect_with_spacy(self, text: str) -> List[PHIEntity]:
        """
        Detect entities using spaCy (integrated from spacy_deidentifier.py).
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected PHI entities
        """
        # Stage 0: Normalize text while maintaining character mapping
        stage0_result = self.text_normalizer.stage0_normalize_and_candidates(text)
        normalized_text = stage0_result["normalized_text"]
        project_fn = stage0_result["project_fn"]
        
        entities = []
        
        # Get the spaCy model from the analyzer's NLP engine
        nlp = self.analyzer.nlp_engine.nlp['en']
        
        # Process the normalized text with spaCy
        doc = nlp(normalized_text)
        
        # spaCy entity mapping (from spacy_deidentifier.py)
        spacy_mapping = {
            "PERSON": "NAME",
            "GPE": "LOCATION",
            "LOC": "LOCATION",
            "FAC": "LOCATION",
            "GEOGRAPHIC_SUBDIVISION": "LOCATION",  # Add this mapping
            "ORG": "ORGANIZATION",
            "DATE": "DATE",
            "TIME": "DATE",
        }
        
        # Convert spaCy entities to PHI entities
        for ent in doc.ents:
            # Map spaCy entity type to our category
            category = spacy_mapping.get(ent.label_, None)
            
            # Debug: Print the mapping
            if ent.label_ == "GPE":
                print(f"DEBUG spaCy: Mapping {ent.label_} -> {category}")
            
            # Skip if not mapped or not in target identifiers
            if category is None or category not in self.target_identifiers:
                continue
            
            # Calculate confidence using the same logic as spacy_deidentifier.py
            confidence = self._get_spacy_confidence(ent)
            
            # Skip if confidence is below threshold
            if confidence < self.threshold:
                continue
            
            # Project span back to original text
            original_start, original_end = project_fn(ent.start_char, ent.end_char)
            
            entity = PHIEntity(
                start=original_start,
                end=original_end,
                category=category,
                confidence=confidence,
                text=text[original_start:original_end]
            )
            entities.append(entity)
        
        return entities
    
    def _get_spacy_confidence(self, ent) -> float:
        """
        Calculate confidence score for spaCy entity (from spacy_deidentifier.py).
        
        Args:
            ent: spaCy entity
            
        Returns:
            Confidence score between 0 and 1
        """
        # Use entity-specific base confidence
        base_confidence = {
            "PERSON": 0.9,    # High confidence for person names
            "GPE": 0.85,      # Good confidence for geo-political entities
            "LOC": 0.8,       # Good confidence for locations
            "FAC": 0.75,      # Moderate confidence for facilities
            "ORG": 0.85,      # Good confidence for organizations
            "DATE": 0.85,     # Good confidence for dates
            "TIME": 0.8       # Good confidence for times
        }.get(ent.label_, 0.7)  # Default confidence
        
        # Add dynamic adjustments based on entity length
        length_factor = min(0.2, (len(ent.text.strip()) - 3) * 0.02)
        
        # Calculate final confidence
        confidence = min(0.95, base_confidence + length_factor)
        
        return confidence
    
    def _detect_clinical_patterns(self, text: str) -> List[PHIEntity]:
        """
        Detect entities using clinical patterns (from spacy_deidentifier.py).
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected PHI entities
        """
        # Stage 0: Normalize text while maintaining character mapping
        stage0_result = self.text_normalizer.stage0_normalize_and_candidates(text)
        normalized_text = stage0_result["normalized_text"]
        project_fn = stage0_result["project_fn"]
        
        entities = []
        
        # Add entities from specialized clinical pattern detectors
        if "NAME" in self.target_identifiers:
            # Detect initials and nicknames
            pattern_entities = detect_initials_and_nicknames(normalized_text)
            for entity in pattern_entities:
                original_start, original_end = project_fn(entity.start, entity.end)
                entity.start = original_start
                entity.end = original_end
                entity.text = text[original_start:original_end]
                entity.source = "presidio_clinical"
                entities.append(entity)
            
            # Detect relatives and contacts
            pattern_entities = detect_relatives_and_contacts(normalized_text)
            for entity in pattern_entities:
                original_start, original_end = project_fn(entity.start, entity.end)
                entity.start = original_start
                entity.end = original_end
                entity.text = text[original_start:original_end]
                entity.source = "presidio_clinical"
                entities.append(entity)
        
        if "ORGANIZATION" in self.target_identifiers:
            # Detect facility names
            pattern_entities = detect_facility_names(normalized_text)
            for entity in pattern_entities:
                original_start, original_end = project_fn(entity.start, entity.end)
                entity.start = original_start
                entity.end = original_end
                entity.text = text[original_start:original_end]
                entity.source = "presidio_clinical"
                entities.append(entity)
        
        return entities
    
    def detect_with_header_patterns(self, text: str) -> List[PHIEntity]:
        """
        Detect PHI entities in header patterns.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected PHI entities
        """
        entities = []
        
        # Common header patterns
        patterns = {
            r"(?i)MRN\s*:?\s*([A-Za-z0-9-]+)": "MRN",
            r"(?i)Medical Record Number\s*:?\s*([A-Za-z0-9-]+)": "MRN",
            r"(?i)SSN\s*:?\s*([0-9]{3}-[0-9]{2}-[0-9]{4})": "US_SSN",
            r"(?i)Social Security\s*:?\s*([0-9]{3}-[0-9]{2}-[0-9]{4})": "US_SSN",
            r"(?i)DOB\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})": "DATE",
            r"(?i)Date of Birth\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})": "DATE",
            r"(?i)Phone\s*:?\s*(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})": "PHONE_NUMBER",
            r"(?i)Fax\s*:?\s*(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})": "FAX_NUMBER",
            r"(?i)Email\s*:?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})": "EMAIL_ADDRESS",
            r"(?i)License\s*:?\s*([A-Za-z0-9-]+)": "LICENSE_NUMBER",
            r"(?i)Device\s*:?\s*([A-Za-z0-9-]+)": "MEDICAL_DEVICE_ID",
            r"(?i)VIN\s*:?\s*([A-Z0-9]{17})": "VEHICLE_ID",
            r"(?i)IP\s*:?\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})": "IP_ADDRESS",
            r"(?i)URL\s*:?\s*(https?://[^\s]+)": "URL",
        }
        
        # Check each pattern
        for pattern, category in patterns.items():
            # Skip if not in target identifiers
            if category not in self.target_identifiers:
                continue
                
            # Find all matches
            for match in re.finditer(pattern, text):
                # Get the value (group 1)
                value = match.group(1)
                start = match.start(1)
                end = match.end(1)
                
                # Create PHI entity
                entity = PHIEntity(
                    start=start,
                    end=end,
                    category=category,
                    confidence=0.9,  # High confidence for header patterns
                    text=value,
                )
                entities.append(entity)
        
        return entities


# Create a singleton instance for easy import
presidio_deidentifier = PresidioDeidentifier()
