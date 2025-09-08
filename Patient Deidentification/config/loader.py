"""
Configuration Loader

This module provides functions for loading, merging, and validating configuration settings.
It supports hierarchical configuration with imports and environment-specific overrides.
"""
import os
import yaml
from typing import Dict, List, Optional, Any, Union
from pathlib import Path


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    pass


def _resolve_path(path: Union[str, Path], base_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolve a configuration file path.
    
    Args:
        path: Path to resolve
        base_dir: Base directory for relative paths
        
    Returns:
        Resolved path as a Path object
    """
    path_obj = Path(path)
    
    # If it's an absolute path, return it directly
    if path_obj.is_absolute():
        return path_obj
        
    # If base_dir is provided, resolve relative to it
    if base_dir:
        base_path = Path(base_dir)
        # If base_dir is a file, use its parent directory
        if base_path.is_file():
            base_path = base_path.parent
        return base_path / path_obj
        
    # Otherwise, resolve relative to current directory
    return path_obj


def _load_yaml_file(file_path: Union[str, Path]) -> Dict:
    """
    Load a YAML file.
    
    Args:
        file_path: Path to the YAML file
        
    Returns:
        Dictionary containing the YAML content
        
    Raises:
        ConfigurationError: If the file cannot be loaded
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        raise ConfigurationError(f"Error loading configuration from {file_path}: {e}")


def _merge_configs(base: Dict, override: Dict) -> Dict:
    """
    Recursively merge two configuration dictionaries.
    
    Args:
        base: Base configuration
        override: Configuration to override base
        
    Returns:
        Merged configuration dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        # If the value is a dictionary and the key exists in base, merge recursively
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = _merge_configs(result[key], value)
        # Otherwise, override the value
        else:
            result[key] = value
            
    return result


def load_config(config_path: Optional[Union[str, Path]] = None, 
                environment: Optional[str] = None,
                overrides: Optional[Dict] = None) -> Dict:
    """
    Load configuration from a file with support for imports and environment-specific settings.
    
    Args:
        config_path: Path to the configuration file. If None, uses default paths.
        environment: Environment name (development, production, testing)
        overrides: Dictionary of configuration overrides
        
    Returns:
        The merged configuration as a dictionary
        
    Raises:
        ConfigurationError: If the configuration cannot be loaded or is invalid
    """
    # Default paths to check in order
    default_paths = [
        "config/main.yaml",
        "config/hipaa_config.yaml",  # For backwards compatibility
        "config.yaml",               # For backwards compatibility
    ]
    
    # Use the provided path or try defaults
    paths_to_try = [config_path] if config_path else default_paths
    
    # Try each path
    config_file = None
    config_data = None
    
    for path in paths_to_try:
        if path and os.path.exists(path):
            config_file = path
            config_data = _load_yaml_file(path)
            break
                
    # If we get here and no valid configuration was found, raise an error
    if config_data is None:
        raise ConfigurationError(
            f"No valid configuration file found. Tried: {', '.join(str(p) for p in paths_to_try)}"
        )
    
    # Process imports if present
    base_dir = os.path.dirname(config_file) if config_file else None
    config = _process_imports(config_data, base_dir)
    
    # Apply environment-specific configuration if specified
    if environment and not environment.endswith('.yaml'):
        env_path = _resolve_path(f"environments/{environment}.yaml", "config")
        if env_path.exists():
            env_config = _load_yaml_file(env_path)
            config = _merge_configs(config, env_config)
    
    # Apply overrides if provided
    if overrides:
        config = _merge_configs(config, overrides)
    
    # Validate the configuration
    _validate_config(config)
    
    return config


def _process_imports(config: Dict, base_dir: Optional[Union[str, Path]] = None) -> Dict:
    """
    Process import directives in the configuration.
    
    Args:
        config: Configuration dictionary
        base_dir: Base directory for resolving relative paths
        
    Returns:
        Merged configuration with imports processed
    """
    result = {}
    
    # Process imports first if present
    if 'imports' in config:
        for import_path in config['imports']:
            import_file = _resolve_path(import_path, base_dir)
            if import_file.exists():
                import_config = _load_yaml_file(import_file)
                # Process nested imports
                import_config = _process_imports(import_config, import_file.parent)
                # Merge with result
                result = _merge_configs(result, import_config)
            else:
                raise ConfigurationError(f"Import file not found: {import_file}")
    
    # Remove imports key
    config_without_imports = {k: v for k, v in config.items() if k != 'imports'}
    
    # Merge with the current config (giving precedence to current config)
    return _merge_configs(result, config_without_imports)


def _validate_config(config: Dict) -> None:
    """
    Validate that the configuration has the required sections.
    
    Args:
        config: The configuration dictionary to validate
        
    Raises:
        ConfigurationError: If the configuration is invalid
    """
    # Required sections
    required_sections = ["detect", "transform"]
    
    for section in required_sections:
        if section not in config:
            raise ConfigurationError(f"Configuration is missing required section: {section}")
            
    # Validate transform section has rules
    if "rules" not in config.get("transform", {}):
        raise ConfigurationError("Configuration is missing 'rules' in the 'transform' section")
        
    # Validate detect section has enable flags
    detect_section = config.get("detect", {})
    if "enable_rules" not in detect_section or "enable_ml" not in detect_section:
        raise ConfigurationError("Configuration is missing 'enable_rules' or 'enable_ml' in the 'detect' section")
        
    # Validate security section if present
    if "security" in config:
        security_section = config["security"]
        if "salt" not in security_section or "date_shift_days" not in security_section:
            raise ConfigurationError("Configuration is missing 'salt' or 'date_shift_days' in the 'security' section")


def get_config_value(config: Dict, path: str, default: Any = None) -> Any:
    """
    Get a value from the configuration using a dot-separated path.
    
    Args:
        config: Configuration dictionary
        path: Dot-separated path to the value (e.g., "models.spacy")
        default: Default value to return if the path is not found
        
    Returns:
        The value at the specified path or the default value
    """
    parts = path.split('.')
    current = config
    
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
            
    return current
