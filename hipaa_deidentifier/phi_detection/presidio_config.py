"""
Presidio Configuration

Configures the Presidio analyzer to use the medium spaCy model.
"""
import os
import spacy
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

# Set the default spaCy model to the medium model
DEFAULT_SPACY_MODEL = "en_core_web_md"

def load_spacy_model():
    """
    Loads the spaCy model, preferring the medium model.
    
    Returns:
        The loaded spaCy model
    """
    try:
        # Try to load the medium model first
        return spacy.load(DEFAULT_SPACY_MODEL)
    except OSError:
        # If that fails, try to download it
        print(f"Downloading spaCy model: {DEFAULT_SPACY_MODEL}")
        spacy.cli.download(DEFAULT_SPACY_MODEL)
        return spacy.load(DEFAULT_SPACY_MODEL)

def create_analyzer_with_medium_model():
    """
    Creates a Presidio analyzer that uses the medium spaCy model.
    
    Returns:
        A configured AnalyzerEngine instance
    """
    # Set environment variable to override Presidio's default
    os.environ["PRESIDIO_SPACY_MODEL"] = DEFAULT_SPACY_MODEL
    
    # Load the medium model first
    nlp = load_spacy_model()
    
    # Create NLP engine provider with explicit configuration
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": DEFAULT_SPACY_MODEL}]
    }
    
    # Create the NLP engine provider with our configuration
    provider = NlpEngineProvider(nlp_configuration=configuration)
    
    # Create the NLP engine
    nlp_engine = provider.create_engine()
    
    # Create the analyzer with our custom NLP engine
    analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
    
    return analyzer