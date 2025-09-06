"""
Model Cache Manager

Manages caching of ML models to avoid repeated downloads.
"""
import os
import json
from typing import Optional, Dict, Any
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline as hf_pipeline
import spacy
from transformers import logging as tf_logging

# Reduce verbosity of transformers warnings
tf_logging.set_verbosity_error()

class ModelCache:
    """
    Singleton class to manage model caching and reuse.
    """
    _instance = None
    _models = {}
    _cache_initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_spacy_model(self, model_name: str) -> Any:
        """
        Get or load a spaCy model with caching.
        
        Args:
            model_name: Name of the spaCy model
            
        Returns:
            The loaded spaCy model
        """
        cache_key = f"spacy_{model_name}"
        
        if cache_key not in self._models:
            try:
                self._models[cache_key] = spacy.load(model_name)
                print(f"✓ Loaded spaCy model from cache: {model_name}")
            except OSError:
                print(f"Downloading spaCy model: {model_name}")
                spacy.cli.download(model_name)
                self._models[cache_key] = spacy.load(model_name)
                print(f"✓ Downloaded and cached spaCy model: {model_name}")
        
        return self._models[cache_key]
    
    def get_hf_pipeline(self, model_name: str, device: int = -1) -> Any:
        """
        Get or load a Hugging Face pipeline with caching.
        
        Args:
            model_name: Name of the Hugging Face model
            device: Device to run on
            
        Returns:
            The loaded Hugging Face pipeline
        """
        # Use model name only for cache key (device doesn't affect the model itself)
        cache_key = f"hf_{model_name}"
        
        if cache_key not in self._models:
            print(f"Loading Hugging Face model: {model_name}")
            try:
                # Set cache directory explicitly
                cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
                os.makedirs(cache_dir, exist_ok=True)
                
                # Load with explicit cache directory
                self._models[cache_key] = hf_pipeline(
                    "token-classification",
                    model=AutoModelForTokenClassification.from_pretrained(
                        model_name,
                        cache_dir=cache_dir
                    ),
                    tokenizer=AutoTokenizer.from_pretrained(
                        model_name,
                        cache_dir=cache_dir
                    ),
                    aggregation_strategy="simple",
                    device=device
                )
                print(f"✓ Loaded Hugging Face model: {model_name}")
            except Exception as e:
                print(f"✗ Error loading Hugging Face model {model_name}: {e}")
                return None
        else:
            print(f"✓ Using previously loaded Hugging Face model: {model_name}")
        
        return self._models[cache_key]
    
    def clear_cache(self):
        """Clear all cached models."""
        self._models.clear()
        self._cache_initialized = False
        print("Model cache cleared")
    
    def list_cached_models(self):
        """List all cached models."""
        print("Cached models:")
        for key in self._models.keys():
            print(f"  - {key}")


# Global model cache instance
model_cache = ModelCache()