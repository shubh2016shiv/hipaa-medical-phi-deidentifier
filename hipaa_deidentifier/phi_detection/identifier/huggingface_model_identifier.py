#!/usr/bin/env python3
"""
Hugging Face Transformer-based De-identifier Module

This module specializes in detecting medical-specific PHI entities using 
Hugging Face transformer models like BERT.

It focuses on identifiers that require medical domain knowledge:
- Medical record numbers (MRN)
- Health plan IDs
- Account numbers
- Biometric identifiers
- Medical-specific identifiers
"""

from typing import Dict, List, Optional

from hipaa_deidentifier.models.phi_entity import PHIEntity
from hipaa_deidentifier.utils.model_cache import model_cache
from hipaa_deidentifier.phi_detection.clinical_patterns import detect_ages_over_89


class HFDeidentifier:
    """
    Specialized de-identifier that uses Hugging Face transformer models for medical PHI detection.
    
    This class focuses on detecting medical-specific identifiers:
    - MRN (Medical Record Numbers)
    - Health plan IDs
    - Account numbers
    - Biometric identifiers
    - Photo IDs
    - Other medical-specific identifiers
    - Ages over 89
    """
    
    # Map HF entity types to our PHI categories (based on i2b2 dataset)
    HF_MAPPING = {
        "PATIENT": "NAME",           # Patient names
        "STAFF": "NAME",             # Staff names  
        "HOSP": "ORGANIZATION",      # Hospital names
        "LOC": "LOCATION",           # Locations
        "DATE": "DATE",              # Dates
        "AGE": "AGE_OVER_89",        # Ages (especially over 89)
        "PHONE": "PHONE_NUMBER",     # Phone numbers
        "ID": "MRN",                 # Medical record numbers/IDs
        "PATORG": "ORGANIZATION",    # Patient organizations
        "EMAIL": "EMAIL_ADDRESS",    # Email addresses
        "OTHERPHI": "UNKNOWN"       # Other PHI -> Map to UNKNOWN instead of OTHER_ID
    }
    
    # Identifiers that HF models are trained on (based on I2B2 dataset)
    # These are the entity types the model was specifically trained to detect
    HF_OPTIMIZED_IDENTIFIERS = {
        "NAME",             # Patient and staff names (PATIENT, STAFF in I2B2) - 25.55%
        "ORGANIZATION",     # Hospital and organizations (HOSP, PATORG in I2B2) - 8.49%
        "LOCATION",         # Locations (LOC in I2B2) - 7.59%
        "DATE",             # Dates (DATE in I2B2) - 44.14%
        "AGE_OVER_89",      # Ages (AGE in I2B2) - 6.77%
        "PHONE_NUMBER",     # Phone numbers (PHONE in I2B2) - 1.92%
        "MRN",              # Medical record numbers (ID in I2B2) - 5.54%
        "EMAIL_ADDRESS"     # Email addresses (EMAIL in I2B2) - 0.01%
        # OTHER_ID removed as per user request
    }
    
    # Threshold map for different confidence levels
    # Based on the inspiration code's threshold values
    THRESHOLD_MAP = {
        "obi/deid_bert_i2b2": {
            "standard": 0.7,           # Default threshold
            "high": 0.85,              # Higher precision
            "very_high": 0.95,         # Very high precision
            "recall_99.5": 4.656e-06,  # 99.5% recall threshold
            "recall_99.7": 1.898e-06   # 99.7% recall threshold
        },
        "obi/deid_roberta_i2b2": {
            "standard": 0.7,           # Default threshold
            "high": 0.85,              # Higher precision
            "very_high": 0.95,         # Very high precision
            "recall_99.5": 2.436e-05,  # 99.5% recall threshold
            "recall_99.7": 2.396e-06   # 99.7% recall threshold
        }
    }
    
    def __init__(self, 
                 hf_model: str = "obi/deid_bert_i2b2", 
                 device: int = -1,
                 config: Optional[Dict] = None,
                 threshold_level: str = "standard"):
        """
        Initialize the Hugging Face transformer-based de-identifier.
        
        Args:
            hf_model: Name or path of the Hugging Face model to use
            device: Device to run inference on (-1 for CPU, 0+ for specific GPU)
            config: Configuration dictionary
            threshold_level: Confidence threshold level (standard, high, very_high, recall_99.5, recall_99.7)
        """
        self.config = config or {}
        
        # Set device
        self.device = device
        self.device_name = "cpu" if device < 0 else f"cuda:{device}"
        
        # Load Hugging Face model and pipeline using model_cache
        self.hf_model_name = hf_model
        self.hf_pipeline = model_cache.get_hf_pipeline(hf_model, device)
        
        # Get targeted identifiers from config or use default
        # Check in detect.hf_identifiers first, then fall back to root hf_identifiers
        detect_config = self.config.get("detect", {})
        self.target_identifiers = detect_config.get("hf_identifiers", 
                                                  self.config.get("hf_identifiers", 
                                                                self.HF_OPTIMIZED_IDENTIFIERS))
        
        # Get detection threshold based on model and threshold level
        threshold_config = self.THRESHOLD_MAP.get(hf_model, {"standard": 0.7})
        config_threshold = self.config.get("detection_thresholds", {}).get("hf")
        
        # Use config threshold if provided, otherwise use the threshold map
        if config_threshold is not None:
            self.threshold = config_threshold
        else:
            self.threshold = threshold_config.get(threshold_level, threshold_config["standard"])
    
    def detect(self, text: str) -> List[PHIEntity]:
        """
        Detect medical-specific PHI entities in the text using the HF model.
        
        Enhanced with better chunking strategy and sentence-aware processing
        inspired by the robust_deid implementation.
        
        Args:
            text: The text to analyze
            
        Returns:
            List of detected PHI entities
        """
        entities = []
        
        # Use the HF pipeline from model_cache
        try:
            # Handle long texts by chunking them to avoid tensor size issues
            if len(text) > 500:
                # Improved chunking with overlap to handle entities at boundaries
                chunk_size = 500
                overlap = 100
                offset = 0
                
                # Split by newlines first to preserve document structure
                paragraphs = text.split('\n')
                for paragraph in paragraphs:
                    # Skip empty paragraphs
                    if not paragraph.strip():
                        offset += len(paragraph) + 1  # +1 for the newline
                        continue
                    
                    # If paragraph is short, process it directly
                    if len(paragraph) <= chunk_size:
                        hf_results = self.hf_pipeline(paragraph)
                        hf_entities = self._process_hf_results(hf_results, offset)
                        entities.extend(hf_entities)
                        offset += len(paragraph) + 1  # +1 for the newline
                    else:
                        # Process long paragraph with overlapping chunks
                        para_offset = 0
                        while para_offset < len(paragraph):
                            end = min(para_offset + chunk_size, len(paragraph))
                            chunk = paragraph[para_offset:end]
                            
                            # Process the chunk
                            hf_results = self.hf_pipeline(chunk)
                            
                            # For overlapping regions, only keep entities fully within the non-overlapping part
                            # except for the last chunk
                            if para_offset > 0 and end < len(paragraph):
                                filtered_results = [
                                    r for r in hf_results 
                                    if r["start"] >= overlap and r["end"] <= len(chunk)
                                ]
                                hf_entities = self._process_hf_results(filtered_results, offset + para_offset)
                            else:
                                hf_entities = self._process_hf_results(hf_results, offset + para_offset)
                                
                            entities.extend(hf_entities)
                            
                            # Move to next chunk with overlap
                            para_offset = end - overlap if end < len(paragraph) else len(paragraph)
                        
                        offset += len(paragraph) + 1  # +1 for the newline
            else:
                # Process short text directly
                hf_results = self.hf_pipeline(text)
                entities = self._process_hf_results(hf_results)
        except Exception as e:
            print(f"Warning: Error in Hugging Face detection: {e}")
            
        # Add specialized detection for ages over 89
        if "AGE_OVER_89" in self.target_identifiers:
            age_entities = detect_ages_over_89(text)
            entities.extend(age_entities)
        
        return entities
    
    def _process_hf_results(self, results: List[dict], offset: int = 0) -> List[PHIEntity]:
        """
        Process results from a Hugging Face pipeline call with robust filtering.
        
        Enhanced with insights from the robust_deid implementation to better handle
        medical-specific entities.
        
        Args:
            results: Results from HF pipeline
            offset: Character offset for chunked texts
            
        Returns:
            List of PHI entities
        """
        entities = []
        
        # Group entities by their type for context-aware processing
        grouped_results = {}
        for result in results:
            entity_type = result["entity_group"]
            if entity_type not in grouped_results:
                grouped_results[entity_type] = []
            grouped_results[entity_type].append(result)
        
        # Process each entity type
        for entity_type, type_results in grouped_results.items():
            # Map HF entity type to our category
            category = self.HF_MAPPING.get(entity_type)
            if not category:
                continue
            
            # Skip if not in target identifiers
            if not self._should_include_category(category):
                continue
            
            # Apply type-specific processing
            for result in type_results:
                # Apply configurable confidence threshold
                if result["score"] < self.threshold:
                    continue
                
                # Get cleaned text
                word = result["word"].strip()
                
                # Skip single character entities (they're usually false positives)
                if len(word) <= 1:
                    continue
                
                # Special handling for different entity types
                if category == "MRN":
                    # For MRNs, require at least one digit and minimum length of 3
                    if not any(c.isdigit() for c in word) or len(word) < 3:
                        continue
                
                elif category == "EMAIL_ADDRESS":
                    # For emails, require @ symbol
                    if "@" not in word:
                        continue
                
                elif category == "PHONE_NUMBER":
                    # For phone numbers, require at least 3 digits
                    if sum(c.isdigit() for c in word) < 3:
                        continue
                
                elif category == "DATE":
                    # For dates, require either digit or month name
                    has_digit = any(c.isdigit() for c in word)
                    month_patterns = ["jan", "feb", "mar", "apr", "may", "jun", 
                                     "jul", "aug", "sep", "oct", "nov", "dec"]
                    has_month = any(month in word.lower() for month in month_patterns)
                    if not (has_digit or has_month):
                        continue
                
                # Create and add the entity
                entity = PHIEntity(
                    start=result["start"] + offset,
                    end=result["end"] + offset,
                    category=category,
                    confidence=float(result["score"]),
                    text=word,
                )
                # Set source for tracking
                entity.source = "hf"
                entities.append(entity)
        
        return entities
    
    def _should_include_category(self, category: str) -> bool:
        """
        Check if a category should be included based on target identifiers.
        
        Args:
            category: The PHI category
            
        Returns:
            True if the category should be included, False otherwise
        """
        # Special case for MRN and related categories
        if category in ["MRN", "HEALTH_PLAN_ID", "ACCOUNT_NUMBER"]:
            return any(id_type in self.target_identifiers 
                      for id_type in ["MRN", "HEALTH_PLAN_ID", "ACCOUNT_NUMBER"])
        
        return category in self.target_identifiers


# Don't create a singleton instance - this should be initialized with proper parameters
# hf_deidentifier = HFDeidentifier()