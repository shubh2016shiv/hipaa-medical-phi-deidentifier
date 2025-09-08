"""
Centralized Configuration Module

This module provides a professional, unified configuration system that consolidates
all configuration loading, model management, and settings access into a single,
well-structured interface.

Key Components:
1. ConfigurationLoader - Handles YAML loading and validation
2. ModelManager - Manages spaCy and Presidio models without environment variables
3. Config - Main interface providing access to settings and models

Author: HIPAA De-identification System
Version: 1.0.0
"""

import os
import yaml
import spacy
from typing import Dict, Any, Optional, Union
from pathlib import Path
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors."""
    pass


class ConfigurationLoader:
    """
    Handles loading and validation of YAML configuration files.

    This class is responsible for:
    - Loading YAML files with proper path resolution
    - Merging base and environment-specific configurations
    - Validating required sections and values
    - Providing clean configuration data to other components
    """

    def __init__(self):
        self._config_cache: Optional[Dict] = None
        self._config_path: Optional[Path] = None

    def load_config(self,
                   config_path: Optional[Union[str, Path]] = None,
                   environment: Optional[str] = None) -> Dict:
        """
        Load configuration from YAML files.

        Args:
            config_path: Path to main config file. If None, uses default paths.
            environment: Environment name (development, production, testing)

        Returns:
            Merged configuration dictionary

        Raises:
            ConfigurationError: If configuration cannot be loaded or is invalid
        """
        if self._config_cache is not None:
            return self._config_cache

        # Default paths to check
        default_paths = [
            "config/main.yaml",
            "config.yaml",
            "hipaa_config.yaml"
        ]

        paths_to_try = [config_path] if config_path else default_paths
        config_data = None
        config_file = None

        # Find and load the main config file
        for path in paths_to_try:
            if path and os.path.exists(path):
                config_file = Path(path)
                config_data = self._load_yaml_file(config_file)
                break

        if config_data is None:
            raise ConfigurationError(
                f"No valid configuration file found. Tried: {', '.join(str(p) for p in paths_to_try)}"
            )

        # Process imports if present
        config = self._process_imports(config_data, config_file.parent)

        # Apply environment-specific overrides
        if environment:
            env_config = self._load_environment_config(environment, config_file.parent)
            if env_config:
                config = self._merge_configs(config, env_config)

        # Validate the final configuration
        self._validate_config(config)

        self._config_cache = config
        self._config_path = config_file

        return config

    def _load_yaml_file(self, file_path: Path) -> Dict:
        """Load a YAML file and return its contents."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise ConfigurationError(f"Error loading configuration from {file_path}: {e}")

    def _process_imports(self, config: Dict, base_dir: Path) -> Dict:
        """Process import directives in configuration."""
        result = {}

        if 'imports' in config:
            for import_path in config['imports']:
                import_file = base_dir / import_path
                if import_file.exists():
                    import_config = self._load_yaml_file(import_file)
                    # Process nested imports
                    import_config = self._process_imports(import_config, import_file.parent)
                    result = self._merge_configs(result, import_config)
                else:
                    raise ConfigurationError(f"Import file not found: {import_file}")

        # Merge current config (giving precedence to current config)
        config_without_imports = {k: v for k, v in config.items() if k != 'imports'}
        return self._merge_configs(result, config_without_imports)

    def _load_environment_config(self, environment: str, base_dir: Path) -> Optional[Dict]:
        """Load environment-specific configuration."""
        env_file = base_dir / "environments" / f"{environment}.yaml"
        if env_file.exists():
            return self._load_yaml_file(env_file)
        return None

    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge two configuration dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def _validate_config(self, config: Dict) -> None:
        """Validate that configuration has all required sections and values."""
        required_sections = ["detect", "transform"]

        for section in required_sections:
            if section not in config:
                raise ConfigurationError(f"Configuration missing required section: {section}")

        # Validate transform section
        transform = config.get("transform", {})
        if "rules" not in transform:
            raise ConfigurationError("Configuration missing 'rules' in 'transform' section")

        # Validate detect section
        detect = config.get("detect", {})
        required_detect_keys = ["enable_rules", "enable_ml"]
        for key in required_detect_keys:
            if key not in detect:
                raise ConfigurationError(f"Configuration missing '{key}' in 'detect' section")

        # Validate models section
        models = config.get("models", {})
        if "spacy" not in models:
            raise ConfigurationError("Configuration missing 'spacy' model in 'models' section")

    def get_value(self, config: Dict, path: str, default: Any = None) -> Any:
        """Get a value from configuration using dot-separated path."""
        parts = path.split('.')
        current = config

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default

        return current


class ModelManager:
    """
    Manages loading and caching of ML models (spaCy, Presidio).

    This class handles:
    - Loading spaCy models without environment variables
    - Creating Presidio analyzers with proper NLP engines
    - Caching loaded models for performance
    - Providing clean interfaces to access models
    """

    def __init__(self):
        self._spacy_models: Dict[str, Any] = {}
        self._analyzers: Dict[str, AnalyzerEngine] = {}

    def load_spacy_model(self, model_name: str) -> Any:
        """
        Load a spaCy model with caching.

        Args:
            model_name: Name of the spaCy model to load

        Returns:
            Loaded spaCy model

        Raises:
            ConfigurationError: If model cannot be loaded
        """
        if model_name in self._spacy_models:
            return self._spacy_models[model_name]

        try:
            # Try to load the model
            nlp = spacy.load(model_name)
            self._spacy_models[model_name] = nlp
            return nlp
        except OSError:
            # If loading fails, try to download it
            try:
                print(f"Downloading spaCy model: {model_name}")
                spacy.cli.download(model_name)
                nlp = spacy.load(model_name)
                self._spacy_models[model_name] = nlp
                return nlp
            except Exception as e:
                raise ConfigurationError(f"Failed to load spaCy model '{model_name}': {e}")

    def create_analyzer(self, spacy_model_name: str) -> AnalyzerEngine:
        """
        Create a Presidio analyzer with the specified spaCy model.

        Args:
            spacy_model_name: Name of the spaCy model to use

        Returns:
            Configured AnalyzerEngine instance

        Raises:
            ConfigurationError: If analyzer cannot be created
        """
        cache_key = f"analyzer_{spacy_model_name}"

        if cache_key in self._analyzers:
            return self._analyzers[cache_key]

        try:
            # Load the spaCy model
            nlp = self.load_spacy_model(spacy_model_name)

            # Create NLP engine provider
            provider = NlpEngineProvider()

            # Create the NLP engine
            nlp_engine = provider.create_engine()

            # Create and cache the analyzer
            analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
            self._analyzers[cache_key] = analyzer

            return analyzer
        except Exception as e:
            raise ConfigurationError(f"Failed to create analyzer with model '{spacy_model_name}': {e}")

    def get_analyzer(self, config: Dict) -> AnalyzerEngine:
        """
        Get a Presidio analyzer using the spaCy model from configuration.

        Args:
            config: Configuration dictionary

        Returns:
            Configured AnalyzerEngine instance
        """
        spacy_model = config.get("models", {}).get("spacy", "en_core_web_lg")
        return self.create_analyzer(spacy_model)


class Config:
    """
    Main configuration interface providing centralized access to settings and models.

    This is the primary interface that other modules should use to access:
    - Configuration settings
    - ML models and analyzers
    - Validation and utility functions

    Usage:
        config = Config.get_instance()
        settings = config.get_settings()
        analyzer = config.get_analyzer()
        threshold = config.get_detection_threshold('presidio')
    """

    _instance = None

    def __init__(self):
        if Config._instance is not None:
            raise ConfigurationError("Config is a singleton class. Use get_instance() instead.")

        self._loader = ConfigurationLoader()
        self._models = ModelManager()
        self._config: Optional[Dict] = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> 'Config':
        """Get the singleton instance of the Config class."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self,
                  config_path: Optional[Union[str, Path]] = None,
                  environment: Optional[str] = None) -> None:
        """
        Initialize the configuration system.

        Args:
            config_path: Path to main config file
            environment: Environment name (development, production, testing)
        """
        if not self._initialized:
            self._config = self._loader.load_config(config_path, environment)
            self._initialized = True

    def get_settings(self) -> Dict:
        """
        Get the full configuration settings.

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationError: If configuration not initialized
        """
        if not self._initialized or self._config is None:
            self.initialize()
            if self._config is None:
                raise ConfigurationError("Failed to load configuration")

        return self._config

    def get_value(self, path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot-separated path.

        Args:
            path: Dot-separated path (e.g., 'models.spacy')
            default: Default value if path not found

        Returns:
            Configuration value or default
        """
        config = self.get_settings()
        return self._loader.get_value(config, path, default)

    def get_detection_config(self) -> Dict:
        """Get detection-related configuration."""
        return self.get_settings().get("detect", {})

    def get_transform_config(self) -> Dict:
        """Get transformation-related configuration."""
        return self.get_settings().get("transform", {})

    def get_models_config(self) -> Dict:
        """Get models-related configuration."""
        return self.get_settings().get("models", {})

    def get_detection_threshold(self, detector_type: str) -> float:
        """Get detection threshold for a specific detector type."""
        thresholds = self.get_value("detection_thresholds", {})
        return thresholds.get(detector_type, 0.5)

    def get_transform_rule(self, entity_type: str) -> str:
        """Get transformation rule for a specific entity type."""
        rules = self.get_value("transform.rules", {})
        return rules.get(entity_type, self.get_value("transform.default_action", "redact"))

    def get_pseudonym_format(self, entity_type: str) -> str:
        """Get pseudonym format for a specific entity type."""
        formats = self.get_value("pseudonym_formats", {})
        return formats.get(entity_type, formats.get("DEFAULT", "{code}"))

    def get_hash_format(self, entity_type: str) -> str:
        """Get hash format for a specific entity type."""
        formats = self.get_value("hash_formats", {})
        return formats.get(entity_type, formats.get("DEFAULT", "{code}"))

    def get_analyzer(self) -> AnalyzerEngine:
        """Get a configured Presidio analyzer."""
        config = self.get_settings()
        return self._models.get_analyzer(config)

    def get_spacy_model(self) -> Any:
        """Get the configured spaCy model."""
        spacy_model_name = self.get_value("models.spacy", "en_core_web_lg")
        return self._models.load_spacy_model(spacy_model_name)

    def reload_config(self) -> None:
        """Reload configuration (useful for testing or dynamic config changes)."""
        self._loader._config_cache = None
        self._initialized = False
        self.initialize()

    # Utility methods for common configuration access patterns
    def get_salt(self) -> str:
        """Get the salt value for hashing."""
        return self.get_value("security.salt", "DEFAULT_SALT")

    def get_date_shift_days(self) -> int:
        """Get the number of days to shift dates."""
        return self.get_value("security.date_shift_days", 30)

    def get_logging_config(self) -> Dict:
        """Get logging configuration."""
        return self.get_settings().get("logging", {"level": "INFO"})

    def get_normalization_config(self) -> Dict:
        """Get normalization configuration."""
        return self.get_settings().get("normalization", {})


# Create a global instance for easy access
config = Config.get_instance()
