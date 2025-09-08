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
from typing import Dict, List, Optional

from config.config import config as global_config
from .models.phi_entity import PHIEntity
from hipaa_deidentifier.phi_detection.normalizer.phi_normalizer import Stage0Normalizer
from .phi_detection.pattern_detector import create_analyzer_engine, detect_phi_with_patterns, detect_phi_with_header_patterns
from .phi_detection.ml_detector import MLEntityDetector
from .phi_detection.clinical_whitelist import clinical_whitelist
from .phi_redaction.phi_redactor import PHIRedactor
from .utils.color_output import colorize_deidentified_text


class HIPAADeidentifier:
    """
    Main class for de-identifying Protected Health Information (PHI) in text.
    
    This class orchestrates the detection and redaction of PHI according to
    HIPAA Safe Harbor guidelines, which requires the removal of 18 types of identifiers.
    """
    
    def __init__(self, config_path: Optional[str] = None, spacy_model: str = "en_core_web_lg", hf_model: str = "obi/deid_bert_i2b2", ml_model: Optional[str] = None, device: int = -1):
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
            # Config is automatically initialized when accessed
            
        # Get configuration
        self.config = config.get_config()
        
        # Initialize the text normalizer (Stage 0)
        self.text_normalizer = Stage0Normalizer()
        
        # Initialize the pattern detector
        self.analyzer = create_analyzer_engine()
        
        # Initialize the ML detector if enabled
        self.ml_detector = None
        if self.config["detect"]["enable_ml"]:
            self.ml_detector = MLEntityDetector(spacy_model, hf_model, device=device)
            
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
                "confidence": round(entity.confidence, 3)
            }
            for entity in entities
        ]
        
        return {
            "text": deidentified_text,
            "entities": audit
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
        Detects PHI entities using a normalized text pipeline.
        
        Stage 0: Normalize text while maintaining character mapping
        Stage 1: Run all detectors on normalized text
        Stage 2: Project detected spans back to original text
        Stage 3: Identify clinical terms to preserve
        Stage 4: Resolve overlaps and prioritize clinical terms
        
        Args:
            text: The text to analyze
            
        Returns:
            A list of detected PHI entities with positions in original text
        """
        # Stage 0: Normalize text while maintaining character mapping
        stage0_result = self.text_normalizer.stage0_normalize_and_candidates(text)
        normalized_text = stage0_result["normalized_text"]
        project_fn = stage0_result["project_fn"]
        
        # Stage 1: Run all detectors on normalized text
        entities = []
        
        # Rule-based detection (Presidio) on normalized text
        if self.config["detect"]["enable_rules"]:
            # Get pattern detection threshold from config
            pattern_threshold = self.config.get("detection_thresholds", {}).get("patterns", 0.5)
            
            # Apply rule-based detection with configured threshold on normalized text
            rule_entities = detect_phi_with_patterns(normalized_text, self.analyzer, threshold=pattern_threshold)
            entities.extend(rule_entities)
            
            # Add header pattern detections with the same threshold on normalized text
            header_entities = detect_phi_with_header_patterns(normalized_text, threshold=pattern_threshold)
            entities.extend(header_entities)
        
        # ML detection on normalized text if enabled
        if self.ml_detector:
            ml_entities = self.ml_detector.detect(normalized_text)
            entities.extend(ml_entities)
        
        # Stage 2: Project all detected spans back to original text
        original_entities = []
        for entity in entities:
            # Project span from normalized text back to original text
            original_span = project_fn(entity.start, entity.end)
            
            # Get the text from the original
            entity_text = text[original_span[0]:original_span[1]]
            
            # Create new entity with original text positions
            original_entity = PHIEntity(
                start=original_span[0],
                end=original_span[1],
                category=entity.category,
                confidence=entity.confidence,
                text=entity_text  # Extract text from original
            )
            original_entities.append(original_entity)
        
        # Stage 3: Identify clinical terms to preserve
        clinical_terms_to_preserve = []
        
        # Find clinical terms in the text
        for start, end, category in clinical_whitelist.find_clinical_terms(text):
            # Create a clinical entity with high confidence to ensure preservation
            clinical_entity = PHIEntity(
                start=start,
                end=end,
                category=category,  # Use the specific clinical category
                confidence=0.99,    # High confidence to ensure preservation
                text=text[start:end]
            )
            clinical_terms_to_preserve.append(clinical_entity)
        
        # Stage 4: Resolve overlaps with clinical term preservation
        # First, filter out entities that overlap with clinical terms
        final_entities = []
        for entity in original_entities:
            # Check if this entity overlaps with any clinical term
            overlaps_with_clinical = False
            for clinical in clinical_terms_to_preserve:
                # Check for overlap
                if (entity.start < clinical.end and entity.end > clinical.start):
                    # Entity overlaps with a clinical term
                    overlaps_with_clinical = True
                    break
            
            # Only keep entities that don't overlap with clinical terms
            if not overlaps_with_clinical:
                final_entities.append(entity)
        
        # Then resolve any remaining overlaps among PHI entities
        from .models.phi_entity import _resolve_overlaps
        return _resolve_overlaps(final_entities)