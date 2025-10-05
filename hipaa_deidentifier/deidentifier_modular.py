#!/usr/bin/env python3
"""
HIPAA De-identifier (Modular Architecture)

Main module that orchestrates the PHI detection and redaction process using
a modular architecture with specialized detectors for different types of identifiers.
"""

"""
Hinglish Comments:

Ye hamara production-grade modular HIPAA De-identifier hai jo medical text se PHI ko detect aur redact karta hai.

Is module ka main purpose hai HIPAA compliance ko ensure karna, lekin ek modular architecture ke saath.
Har type ke identifier ke liye ek specialized detector use karta hai:

1. Presidio - structured data ke liye (phone, email, SSN, etc.)
2. spaCy - general entities ke liye (names, locations, organizations, dates)
3. BERT - medical-specific entities ke liye (MRN, health plan IDs, etc.)

Ye approach har identifier ko uske best-suited detector se process karta hai, 
jisse accuracy improve hoti hai aur over/under-redaction kam hota hai.
"""

import re
from typing import Dict, List, Optional

from config.config import config as global_config
from .models.phi_entity import PHIEntity
from hipaa_deidentifier.phi_detection.normalizer.phi_normalizer import Stage0Normalizer
from hipaa_deidentifier.phi_detection.identifier.presidio_identifier import PresidioDeidentifier
from hipaa_deidentifier.phi_detection.identifier.huggingface_model_identifier import HFDeidentifier
# Note: spaCy functionality is now integrated into PresidioDeidentifier
from .phi_redaction.phi_redactor import PHIRedactor
from .utils.color_output import colorize_deidentified_text


class HIPAADeidentifierModular:
    """
    Main class for de-identifying Protected Health Information (PHI) in text.
    
    This class orchestrates the detection and redaction of PHI according to
    HIPAA Safe Harbor guidelines, using a modular architecture with specialized
    detectors for different types of identifiers.
    """
    
    def __init__(self, config_path: Optional[str] = None, spacy_model: Optional[str] = None, hf_model: Optional[str] = None, device: int = -1):
        """
        Initializes the de-identifier with the specified configuration.
        
        Args:
            config_path: Path to the configuration file
            spacy_model: Name of the spaCy model to use for entity detection
            hf_model: Name of the Hugging Face model to use for entity detection
            device: Device to run ML inference on (-1 for CPU, 0+ for specific GPU)
        """
        # Get configuration from global config
        self.config = global_config.get_settings()
        
        # Use configuration defaults if parameters not provided
        if spacy_model is None:
            spacy_model = self.config.get("models", {}).get("spacy", "en_core_web_lg")
        if hf_model is None:
            hf_model = self.config.get("models", {}).get("huggingface", "obi/deid_bert_i2b2")
        if device == -1:  # Only use config default if device is not explicitly set
            device = self.config.get("models", {}).get("device", -1)
        
        # Initialize the text normalizer (Stage 0)
        self.text_normalizer = Stage0Normalizer()
        
        # Initialize specialized detectors
        
        # 1. Presidio for structured data (phone, email, SSN, etc.)
        self.presidio_detector = PresidioDeidentifier(config=self.config)
        
        # 2. spaCy functionality is now integrated into Presidio (using large model)
        # self.spacy_detector = SpacyDeidentifier(model_name=spacy_model, config=self.config)
        
        # 2. HF/BERT for medical-specific entities (MRN, health plan IDs, etc.)
        if self.config["detect"]["enable_ml"]:
            self.hf_detector = HFDeidentifier(
                hf_model=hf_model,
                device=device,
                config=self.config
            )
        else:
            self.hf_detector = None
            
        # Initialize the redactor
        self.redactor = PHIRedactor(self.config)
    
    def deidentify(self, text: str, patient_id: Optional[str] = None) -> Dict:
        """
        De-identifies PHI in the given text.
        
        Args:
            text: The text to de-identify
            patient_id: Optional patient identifier for consistent pseudonyms and date shifting
            
        Returns:
            A dictionary containing the de-identified text and detected entities
        """
        # Detect PHI entities
        entities = self._detect_phi(text)
        
        # Redact the detected PHI
        deidentified_text = self.redactor.redact_text(text, entities, patient_id)
        
        # Create audit record (without the actual PHI text)
        audit = [
            {
                "start": entity.start,
                "end": entity.end,
                "category": entity.category,
                "confidence": round(entity.confidence, 3),
                "source": getattr(entity, "source", "unknown")  # Include source if available
            }
            for entity in entities
        ]
        
        return {
            "text": deidentified_text,
            "entities": audit  # Return serializable audit dicts
        }
    
    def deidentify_with_colors(self, text: str, patient_id: Optional[str] = None) -> Dict:
        """
        De-identifies PHI in the given text and returns results with colored text.
        
        Args:
            text: The text to de-identify
            patient_id: Optional patient identifier for consistent pseudonyms and date shifting
            
        Returns:
            A dictionary containing the de-identified text, detected entities, and colorized text
        """
        # Get standard de-identification results
        result = self.deidentify(text, patient_id)
        
        # Add colorized text
        result["colorized_text"] = colorize_deidentified_text(result["text"], result["entities"])
        
        return result
    
    def _detect_phi(self, text: str) -> List[PHIEntity]:
        """
        Detects PHI entities using a modular pipeline with specialized detectors.
        
        Stage 0: Normalize text while maintaining character mapping
        Stage 1: Run specialized detectors on normalized text
        Stage 2: Project detected spans back to original text
        Stage 3: Resolve overlaps and return final entities
        
        Args:
            text: The text to analyze
            
        Returns:
            A list of detected PHI entities with positions in original text
        """
        # Stage 0: Normalize text while maintaining character mapping
        stage0_result = self.text_normalizer.stage0_normalize_and_candidates(text)
        normalized_text = stage0_result["normalized_text"]
        project_fn = stage0_result["project_fn"]
        
        # Stage 1: Run specialized detectors on normalized text in sequence
        presidio_entities = []
        
        # 1.1: Presidio for structured data (if enabled)
        if self.config["detect"]["enable_rules"]:
            presidio_entities.extend(self.presidio_detector.detect(normalized_text))
            
            # Also detect header patterns
            presidio_entities.extend(self.presidio_detector.detect_with_header_patterns(normalized_text))
            
            # Create a masked version of the text for the next stage
            # This prevents the HF model from re-detecting what Presidio already found.
            # We replace with '#' to preserve character indices and sentence structure.
            masked_text_for_hf = list(normalized_text)
            for entity in presidio_entities:
                for i in range(entity.start, entity.end):
                    if i < len(masked_text_for_hf):
                        masked_text_for_hf[i] = '#'
            masked_text_for_hf = "".join(masked_text_for_hf)
        else:
            masked_text_for_hf = normalized_text
        
        # 1.2: spaCy functionality is now integrated into Presidio
        
        # 1.3: HF/BERT runs on the masked text to find contextual entities
        hf_entities = []
        if self.hf_detector:
            hf_entities = self.hf_detector.detect(masked_text_for_hf)

        # Combine all entities from all stages
        entities = presidio_entities + hf_entities
        
        # Stage 2: Project all detected spans back to original text
        original_entities = []
        for entity in entities:
            # Project span from normalized text back to original text
            original_span = project_fn(entity.start, entity.end)
            
            # Create new entity with original text positions
            original_entity = PHIEntity(
                start=original_span[0],
                end=original_span[1],
                category=entity.category,
                confidence=entity.confidence,
                text=text[original_span[0]:original_span[1]]  # Extract text from original
            )
            original_entity.source = getattr(entity, "source", "unknown")  # Preserve the source
            original_entities.append(original_entity)
        
        # Stage 3: Merge related entities (like date components and MRN parts)
        merged_entities = self._merge_related_entities(original_entities, text)
        
        # Stage 4: Resolve overlaps with confidence-based voting
        return self._resolve_overlaps_with_confidence(merged_entities)
    
    def _resolve_overlaps_with_confidence(self, entities: List[PHIEntity]) -> List[PHIEntity]:
        """
        Resolve overlapping entities using confidence-based voting.
        
        When entities overlap, choose the one with the highest confidence,
        with preference given to specialized detectors for their target identifiers.
        
        Args:
            entities: List of detected PHI entities
            
        Returns:
            List of non-overlapping PHI entities
        """
        if not entities:
            return []
        
        # Sort entities by start position, then by end position (longer spans first)
        sorted_entities = sorted(entities, key=lambda e: (e.start, -e.end))
        
        # Detector weights for voting
        detector_weights = {
            # Presidio is best for structured data
            "presidio": {
                "PHONE_NUMBER": 1.2, "FAX_NUMBER": 1.2, "EMAIL_ADDRESS": 1.2,
                "US_SSN": 1.2, "URL": 1.2, "IP_ADDRESS": 1.2,
                "LICENSE_NUMBER": 1.2, "VEHICLE_ID": 1.2, "MEDICAL_DEVICE_ID": 1.2,
                "DEFAULT": 0.8  # Lower weight for other categories
            },
            # spaCy is best for general entities
            "spacy": {
                "NAME": 1.2, "LOCATION": 1.2, "ORGANIZATION": 1.2, "DATE": 1.2,
                "DEFAULT": 0.8  # Lower weight for other categories
            },
            # HF is best for medical-specific entities
            "hf": {
                "MRN": 1.2, "HEALTH_PLAN_ID": 1.2, "ACCOUNT_NUMBER": 1.2,
                "BIOMETRIC_ID": 1.2, "PHOTO_ID": 1.2, 
                # OTHER_ID removed as per user request
                "AGE_OVER_89": 1.2,
                "DEFAULT": 0.8  # Lower weight for other categories
            },
            # Default for unknown sources
            "unknown": {
                "DEFAULT": 1.0
            }
        }
        
        # Function to calculate weighted confidence
        def weighted_confidence(entity: PHIEntity) -> float:
            source = getattr(entity, "source", "unknown")
            source_weights = detector_weights.get(source, detector_weights["unknown"])
            weight = source_weights.get(entity.category, source_weights["DEFAULT"])
            return entity.confidence * weight
        
        # Resolve overlaps
        final_entities = []
        for entity in sorted_entities:
            # Check if this entity overlaps with any in the final list
            overlaps = False
            for final_entity in final_entities:
                if (entity.start < final_entity.end and entity.end > final_entity.start):
                    overlaps = True
                    # If this entity has higher weighted confidence, replace the final entity
                    if weighted_confidence(entity) > weighted_confidence(final_entity):
                        final_entities.remove(final_entity)
                        final_entities.append(entity)
                    break
            
            # If no overlap, add to final list
            if not overlaps:
                final_entities.append(entity)
        
        # Sort final entities by position
        return sorted(final_entities, key=lambda e: e.start)
        
    def _merge_related_entities(self, entities: List[PHIEntity], text: str) -> List[PHIEntity]:
        """
        Merge related entities like date components and MRN parts.
        
        For example, merge "03/22" and "1975" into a complete date "03/22/1975".
        
        Args:
            entities: List of detected PHI entities
            text: The original text
            
        Returns:
            List of merged PHI entities
        """
        if not entities:
            return []
            
        # Sort entities by start position
        sorted_entities = sorted(entities, key=lambda e: e.start)
        
        # First pass: identify date components
        date_components = []
        for i, entity in enumerate(sorted_entities):
            if entity.category == "DATE":
                date_components.append(i)
        
        # Second pass: merge adjacent date components
        merged_dates = []
        i = 0
        while i < len(date_components):
            current_idx = date_components[i]
            current = sorted_entities[current_idx]
            
            # Look for adjacent date components
            if i + 1 < len(date_components):
                next_idx = date_components[i + 1]
                next_entity = sorted_entities[next_idx]
                
                # Check if they are close enough (within 5 characters)
                if next_entity.start - current.end <= 5:
                    # Check the text between them
                    between_text = text[current.end:next_entity.start]
                    
                    # If it's just a separator like "/" or "-" or whitespace
                    if between_text.strip() in ["", "/", "-", "."]:
                        # Create a merged entity
                        merged_entity = PHIEntity(
                            start=current.start,
                            end=next_entity.end,
                            category="DATE",
                            confidence=max(current.confidence, next_entity.confidence),
                            text=text[current.start:next_entity.end]
                        )
                        # Preserve source from the entity with higher confidence
                        merged_entity.source = current.source if current.confidence >= next_entity.confidence else next_entity.source
                        merged_dates.append((current_idx, next_idx, merged_entity))
                        i += 2  # Skip both entities
                        continue
            
            i += 1
        
        # Third pass: identify MRN components
        mrn_components = []
        for i, entity in enumerate(sorted_entities):
            if entity.category == "MRN":
                mrn_components.append(i)
        
        # Fourth pass: merge adjacent MRN components
        merged_mrns = []
        i = 0
        while i < len(mrn_components):
            current_idx = mrn_components[i]
            current = sorted_entities[current_idx]
            
            # Look for adjacent MRN components
            if i + 1 < len(mrn_components):
                next_idx = mrn_components[i + 1]
                next_entity = sorted_entities[next_idx]
                
                # Check if they are close enough (within 5 characters)
                if next_entity.start - current.end <= 5:
                    # Create a merged entity
                    merged_entity = PHIEntity(
                        start=current.start,
                        end=next_entity.end,
                        category="MRN",
                        confidence=max(current.confidence, next_entity.confidence),
                        text=text[current.start:next_entity.end]
                    )
                    # Preserve source from the entity with higher confidence
                    merged_entity.source = current.source if current.confidence >= next_entity.confidence else next_entity.source
                    merged_mrns.append((current_idx, next_idx, merged_entity))
                    i += 2  # Skip both entities
                    continue
            
            i += 1
            
        # Fifth pass: identify and merge adjacent NAME components
        name_components = []
        for i, entity in enumerate(sorted_entities):
            if entity.category == "NAME":
                name_components.append(i)

        merged_names = []
        i = 0
        while i < len(name_components):
            current_idx = name_components[i]
            current = sorted_entities[current_idx]
            
            # Look for adjacent NAME components
            if i + 1 < len(name_components):
                next_idx = name_components[i + 1]
                next_entity = sorted_entities[next_idx]
                
                # Check if they are close enough (within 3 characters of whitespace or punctuation)
                if next_entity.start - current.end <= 3:
                    between_text = text[current.end:next_entity.start]
                    if re.match(r'^[\s\.]*$', between_text):  # Allow whitespace and periods
                        # Create a merged entity
                        merged_entity = PHIEntity(
                            start=current.start,
                            end=next_entity.end,
                            category="NAME",
                            confidence=max(current.confidence, next_entity.confidence),
                            text=text[current.start:next_entity.end]
                        )
                        merged_entity.source = current.source if current.confidence >= next_entity.confidence else next_entity.source
                        merged_names.append((current_idx, next_idx, merged_entity))
                        i += 2  # Skip both entities
                        continue
            i += 1
        
        # Apply merges (from end to start to preserve indices)
        result = sorted_entities.copy()
        
        # Sort merges by the first index in reverse order
        all_merges = sorted(merged_dates + merged_mrns + merged_names, key=lambda x: x[0], reverse=True)
        
        for first_idx, second_idx, merged_entity in all_merges:
            # Remove the two original entities
            result.pop(second_idx)
            result.pop(first_idx)
            
            # Add the merged entity
            result.append(merged_entity)
        
        # Sort again by start position
        return sorted(result, key=lambda e: e.start)


# For backwards compatibility
HIPAADeidentifier = HIPAADeidentifierModular
