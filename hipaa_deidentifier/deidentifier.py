"""
HIPAA De-identifier

Main module that orchestrates the PHI detection and redaction process.
"""

"""
Hinglish Comments:

Ye hamara production-grade HIPAA De-identifier hai jo medical text se PHI (Protected Health Information) ko detect aur redact karta hai.

Is module ka main purpose hai HIPAA compliance ko ensure karna. HIPAA ek US healthcare law hai jo patient ki privacy ko protect karta hai. 
Iske according, 18 types ke identifiers ko medical data se remove karna zaroori hai, jaise patient name, phone number, address, etc.

Ye module enterprise-grade hai aur real-world production environment ke liye design kiya gaya hai. Isme:

1. Robust configuration management - YAML files se configuration load karta hai
2. Comprehensive PHI detection - Multiple techniques ka use karta hai (rules + ML)
3. Flexible redaction strategies - Different types ke PHI ke liye different redaction methods
4. Performance optimization - Model caching aur efficient processing
5. Detailed audit logs - Har detected entity ka record rakhta hai

Ye module 'deid_patient_notes' se more structured aur production-ready hai. Dono modules same problem solve karte hain, 
lekin ye module more enterprise-focused hai, jabki deid_patient_notes more experimental aur research-oriented hai.

Ye module HIPAA Safe Harbor guidelines ke according 18 types ke identifiers ko handle karta hai aur high accuracy ke saath 
unko detect aur redact karta hai taaki medical data safely share kiya ja sake.
"""
from typing import Dict, List, Optional, Tuple

from config.manager import config
from .models.phi_entity import PHIEntity, merge_overlapping_entities
from .phi_detection.pattern_detector import create_analyzer_engine, detect_phi_with_patterns, detect_phi_with_header_patterns
from .phi_detection.ml_detector import MLEntityDetector
from .phi_redaction.phi_redactor import PHIRedactor


class HIPAADeidentifier:
    """
    Main class for de-identifying Protected Health Information (PHI) in text.
    
    This class orchestrates the detection and redaction of PHI according to
    HIPAA Safe Harbor guidelines, which requires the removal of 18 types of identifiers.
    """
    
    def __init__(self, config_path: Optional[str] = None, spacy_model: str = "en_core_web_md", hf_model: str = "obi/deid_bert_i2b2", ml_model: Optional[str] = None, device: int = -1):
        """
        Initializes the de-identifier with the specified configuration.
        
        Args:
            config_path: Path to the configuration file
            spacy_model: Name of the spaCy model to use for entity detection
            hf_model: Name of the Hugging Face model to use for entity detection
            ml_model: Alternative parameter name for hf_model (for backwards compatibility)
            device: Device to run ML inference on (-1 for CPU, 0+ for specific GPU)
        """
        # For backwards compatibility, ml_model can be used instead of hf_model
        if ml_model and not hf_model:
            hf_model = ml_model
        # Initialize configuration manager if config_path is provided
        if config_path:
            from config.manager import ConfigManager
            ConfigManager.initialize(config_path=config_path)
            
        # Get configuration
        self.config = config.get_config()
        
        # Initialize the pattern detector
        self.analyzer = create_analyzer_engine()
        
        # Initialize the ML detector if enabled
        self.ml_detector = None
        if self.config["detect"]["enable_ml"]:
            self.ml_detector = MLEntityDetector(spacy_model, hf_model, device=device)
            
        # Initialize the redactor
        self.redactor = PHIRedactor(self.config)
        
    def deidentify(self, text: str) -> Dict:
        """
        De-identifies PHI in the given text.
        
        Args:
            text: The text to de-identify
            
        Returns:
            A dictionary containing the de-identified text and detected entities
        """
        # Detect PHI entities
        entities = self._detect_phi(text)
        
        # Redact the detected PHI
        deidentified_text = self.redactor.redact_text(text, entities)
        
        # Create audit record (without the actual PHI text)
        audit = [
            {
                "start": entity.start,
                "end": entity.end,
                "category": entity.category,
                "confidence": round(entity.confidence, 3)
            }
            for entity in entities
        ]
        
        return {
            "text": deidentified_text,
            "entities": audit
        }
        
    def _detect_phi(self, text: str) -> List[PHIEntity]:
        """
        Detects PHI entities using all enabled detection methods.
        
        Args:
            text: The text to analyze
            
        Returns:
            A list of detected PHI entities with overlaps resolved
        """
        rule_entities = []
        ml_entities = []
        
        # Rule-based detection
        if self.config["detect"]["enable_rules"]:
            rule_entities = detect_phi_with_patterns(text, self.analyzer)
            
            # Add header pattern detections
            header_entities = detect_phi_with_header_patterns(text)
            rule_entities.extend(header_entities)
            
        # ML-based detection
        if self.ml_detector:
            ml_entities = self.ml_detector.detect(text)
            
        # Merge and resolve overlapping entities
        return merge_overlapping_entities(rule_entities, ml_entities)
