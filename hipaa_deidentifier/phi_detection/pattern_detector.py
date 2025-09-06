"""
Pattern-based PHI Detector

Uses rule-based patterns to detect PHI entities in text.
"""
import re
from typing import List, Dict

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from ..models.phi_entity import PHIEntity
from .custom_recognizers import MedicalRecordNumberRecognizer, EncounterIdentifierRecognizer, AgeOver89Recognizer
from .hipaa_recognizers import HealthPlanIDRecognizer, VehicleIDRecognizer, BiometricIDRecognizer, PhotoIDRecognizer, OtherIDRecognizer
from .presidio_config import create_analyzer_with_medium_model


def create_analyzer_engine() -> AnalyzerEngine:
    """
    Creates and configures a Presidio analyzer engine with custom recognizers.
    
    Returns:
        A configured AnalyzerEngine instance
    """
    # Create analyzer with medium model
    analyzer = create_analyzer_with_medium_model()
    
    # Get the registry and add custom healthcare recognizers
    registry = analyzer.registry
    
    # Add basic medical recognizers
    registry.add_recognizer(MedicalRecordNumberRecognizer())
    registry.add_recognizer(EncounterIdentifierRecognizer())
    registry.add_recognizer(AgeOver89Recognizer())
    
    # Add HIPAA-specific recognizers for all 18 identifiers
    registry.add_recognizer(HealthPlanIDRecognizer())
    registry.add_recognizer(VehicleIDRecognizer())
    registry.add_recognizer(BiometricIDRecognizer())
    registry.add_recognizer(PhotoIDRecognizer())
    registry.add_recognizer(OtherIDRecognizer())
    
    return analyzer


def detect_phi_with_patterns(text: str, analyzer: AnalyzerEngine) -> List[PHIEntity]:
    """
    Detects PHI entities using pattern-based rules.
    
    Args:
        text: The text to analyze
        analyzer: The configured analyzer engine
        
    Returns:
        A list of detected PHI entities
    """
    # Run the analyzer
    results = analyzer.analyze(text=text, language="en")
    
    # Convert results to PHIEntity objects
    entities = []
    for result in results:
        entity = PHIEntity(
            start=result.start,
            end=result.end,
            category=result.entity_type,
            confidence=result.score,
            text=text[result.start:result.end]
        )
        entities.append(entity)
        
    return entities


def detect_phi_with_header_patterns(text: str) -> List[PHIEntity]:
    """
    Detects PHI in common header patterns that might be missed by other methods.
    
    Args:
        text: The text to analyze
        
    Returns:
        A list of detected PHI entities
    """
    entities = []
    
    # Patient name in header
    for match in re.finditer(r"(?i)\bPatient\s*(?:Name)?\s*:\s*([A-Z][a-zA-Z\-\s']{1,60})", text):
        start, end = match.span(1)
        entities.append(PHIEntity(
            start=start,
            end=end,
            category="NAME",
            confidence=0.85,
            text=match.group(1)
        ))
    
    # Doctor name in header
    for match in re.finditer(r"(?i)\b(?:Doctor|Dr|Physician|Provider)\s*(?:Name)?\s*:\s*([A-Z][a-zA-Z\-\s']{1,60})", text):
        start, end = match.span(1)
        entities.append(PHIEntity(
            start=start,
            end=end,
            category="NAME",
            confidence=0.85,
            text=match.group(1)
        ))
        
    return entities
