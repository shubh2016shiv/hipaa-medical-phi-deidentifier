"""
Configuration Manager

This module provides a centralized configuration manager for the application.
It handles loading, caching, and accessing configuration settings.
"""
import os
from typing import Dict, Any, Optional, Union
from pathlib import Path

from .loader import load_config, get_config_value, ConfigurationError


class ConfigManager:
    """
    Centralized configuration manager.
    
    This class provides a singleton interface for accessing configuration settings
    across the application.
    """
    _instance = None
    _config = None
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    def initialize(cls, 
                   config_path: Optional[Union[str, Path]] = None,
                   environment: Optional[str] = None,
                   overrides: Optional[Dict] = None) -> None:
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file
            environment: Environment name (development, production, testing)
            overrides: Dictionary of configuration overrides
            
        Raises:
            ConfigurationError: If the configuration cannot be loaded
        """
        # Determine environment from environment variable if not provided
        if environment is None:
            environment = os.environ.get('HIPAA_ENVIRONMENT', 'development')
            
        # Load the configuration
        cls._config = load_config(config_path, environment, overrides)
    
    @classmethod
    def get_config(cls) -> Dict:
        """
        Get the full configuration dictionary.
        
        Returns:
            The configuration dictionary
            
        Raises:
            ConfigurationError: If the configuration has not been initialized
        """
        if cls._config is None:
            cls.initialize()
            
        return cls._config
    
    @classmethod
    def get(cls, path: str, default: Any = None) -> Any:
        """
        Get a configuration value using a dot-separated path.
        
        Args:
            path: Dot-separated path to the configuration value
            default: Default value to return if the path is not found
            
        Returns:
            The configuration value or the default
            
        Raises:
            ConfigurationError: If the configuration has not been initialized
        """
        config = cls.get_config()
        return get_config_value(config, path, default)
    
    @classmethod
    def reset(cls) -> None:
        """Reset the configuration manager."""
        cls._config = None


# Create a singleton instance for easy import
config = ConfigManager()
