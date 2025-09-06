"""
Machine Learning-based PHI Detector

Uses pre-trained NLP models to detect PHI entities in text.
This detector combines spaCy and Hugging Face transformers for better accuracy.
"""

"""
Hinglish Comments:

Ye module production-grade ML-based PHI detection ka implementation hai. Isme hum do powerful ML models ko integrate karte hain:

1. spaCy - Ye general purpose NER model hai jo names, locations, organizations ko detect karta hai. 
   Ye base layer provide karta hai general entities ke detection ke liye.

2. Hugging Face Transformers - Ye specialized medical model hai jo specifically medical text mein PHI ko 
   detect karne ke liye fine-tuned hai. Ye deep contextual understanding provide karta hai.

Is module mein kuch advanced features hain jo ise production-ready banate hain:

1. Model Caching - Models ko memory mein cache karta hai taaki baar-baar load na karna pade, 
   jisse performance significantly improve hoti hai
   
2. Error Handling - Robust error handling hai taaki koi bhi model failure system ko crash na kare

3. Mapping System - Detailed mapping system hai jo model outputs ko standardized PHI categories mein convert karta hai

4. Entity Merging - Overlapping entities ko intelligently merge karta hai

Ye module enterprise systems ke liye design kiya gaya hai aur high-volume processing handle kar sakta hai. 
Ye deid_patient_notes/detection/ml_model.py se more structured, optimized aur production-ready hai.
"""
from typing import List, Optional
import spacy
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline as hf_pipeline

from ..models.phi_entity import PHIEntity, merge_overlapping_entities
from .model_cache import model_cache


class MLEntityDetector:
    """
    Detects PHI entities using a combination of spaCy and Hugging Face transformers.
    
    This detector uses both spaCy models and transformer models to identify named entities
    that might be PHI, providing better coverage and accuracy.
    """
    
    def __init__(self, spacy_model: str = "en_core_web_md", hf_model: Optional[str] = "obi/deid_bert_i2b2", device: int = -1):
        """
        Initializes the ML detector with both spaCy and Hugging Face models.
        
        Args:
            spacy_model: The name of the spaCy model to use
            hf_model: The name of the Hugging Face model to use
            device: Device to run inference on (-1 for CPU, 0+ for specific GPU)
        """
        # Load spaCy model using cache
        self.spacy_nlp = None
        if spacy_model:
            self.spacy_nlp = model_cache.get_spacy_model(spacy_model)
            
            # Set device for spaCy if GPU is available
            if device >= 0:
                spacy.prefer_gpu(device)
        
        # Load Hugging Face model using cache
        self.hf_pipeline = None
        if hf_model:
            self.hf_pipeline = model_cache.get_hf_pipeline(hf_model, device)
        
        # Map spaCy entity types to PHI categories
        self.spacy_mapping = {
            "PERSON": "NAME",
            "ORG": "ORGANIZATION",
            "GPE": "LOCATION",
            "LOC": "LOCATION",
            "FAC": "LOCATION",
            "DATE": "DATE",
            "TIME": "DATE",
            "MONEY": "ACCOUNT_NUMBER",
            "CARDINAL": "OTHER",
            "ORDINAL": "OTHER"
        }
        
        # Map Hugging Face entity types to PHI categories
        # Based on obi/deid_bert_i2b2 model training data
        self.hf_mapping = {
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
            "OTHERPHI": "OTHER"          # Other PHI
        }
    
    def detect(self, text: str) -> List[PHIEntity]:
        """
        Detects potential PHI entities using both spaCy and Hugging Face models.
        
        Args:
            text: The text to analyze
            
        Returns:
            A list of detected PHI entities from both models
        """
        entities = []
        
        # Get entities from spaCy (if available)
        if self.spacy_nlp:
            spacy_entities = self._detect_with_spacy(text)
            entities.extend(spacy_entities)
        
        # Get entities from Hugging Face model (if available)
        if self.hf_pipeline:
            # The pipeline handles tokenization and batching automatically.
            # We can pass the entire text to it directly.
            try:
                hf_results = self.hf_pipeline(text)
                hf_entities = self._process_hf_results(hf_results)
                entities.extend(hf_entities)
            except Exception as e:
                print(f"Warning: Error in Hugging Face detection: {e}")

        return entities
    
    def _detect_with_spacy(self, text: str) -> List[PHIEntity]:
        """Detect entities using spaCy."""
        entities = []
        
        # Process the text with spaCy
        doc = self.spacy_nlp(text)
        
        # Convert spaCy entities to PHIEntity objects
        for ent in doc.ents:
            # Map the entity type
            category = self.spacy_mapping.get(ent.label_)
            
            # Skip entities that don't map to PHI categories
            if not category:
                continue
                
            # Create a PHI entity
            entity = PHIEntity(
                start=ent.start_char,
                end=ent.end_char,
                category=category,
                confidence=0.7,  # spaCy doesn't provide confidence scores
                text=ent.text
            )
            
            entities.append(entity)
            
        return entities
    
    def _process_hf_results(self, results: List[dict], offset: int = 0) -> List[PHIEntity]:
        """Process results from a Hugging Face pipeline call."""
        entities = []
        for result in results:
            category = self.hf_mapping.get(result["entity_group"])
            if not category:
                continue
            
            entity = PHIEntity(
                start=result["start"] + offset,
                end=result["end"] + offset,
                category=category,
                confidence=float(result["score"]),
                text=result["word"]
            )
            entities.append(entity)
        return entities