"""
Configuration Loader

Loads and validates configuration for the HIPAA de-identification process.
"""

"""
Hinglish Comments:

Ye module configuration management ka core component hai. Iska main kaam hai YAML configuration files ko load 
aur validate karna, taaki system ke behavior ko customize kiya ja sake without code changes.

Configuration management enterprise systems mein bahut important hota hai, kyunki:

1. Different environments ke liye different settings chahiye hote hain (dev, staging, production)

2. Different clients/hospitals ke liye customization zaruri hoti hai

3. System behavior ko runtime pe change karna possible hona chahiye

Is module mein kuch important features hain:

1. Flexible Path Resolution - Multiple possible paths check karta hai configuration ke liye

2. Validation Logic - Configuration mein required sections aur values check karta hai

3. Error Handling - Clear error messages deta hai agar configuration invalid ho

4. Default Values - Missing values ke liye sensible defaults provide karta hai

Ye module production environment mein reliability aur maintainability ensure karta hai. 
Configuration changes ko easily apply karne ka capability deta hai without needing code changes.
"""
import os
import yaml
from typing import Dict, Optional


def load_config(config_path: Optional[str] = None) -> Dict:
    """
    Loads the configuration from a YAML file.
    
    Args:
        config_path: Path to the configuration file. If None, uses default paths.
        
    Returns:
        The configuration as a dictionary
        
    Raises:
        FileNotFoundError: If the configuration file cannot be found
        ValueError: If the configuration is invalid
    """
    # Default paths to check in order
    default_paths = [
        "hipaa_config.yaml",
        "config/hipaa_config.yaml",
        "config.yaml",
        "config/config.yaml",
    ]
    
    # Use the provided path or try defaults
    paths_to_try = [config_path] if config_path else default_paths
    
    # Try each path
    for path in paths_to_try:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    _validate_config(config)
                    return config
            except Exception as e:
                print(f"Error loading configuration from {path}: {e}")
                
    # If we get here, no valid configuration was found
    raise FileNotFoundError(
        f"No valid configuration file found. Tried: {', '.join(paths_to_try)}"
    )


def _validate_config(config: Dict) -> None:
    """
    Validates that the configuration has the required sections.
    
    Args:
        config: The configuration dictionary to validate
        
    Raises:
        ValueError: If the configuration is missing required sections
    """
    required_sections = ["detect", "transform", "security"]
    
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Configuration is missing required section: {section}")
            
    # Validate transform section has rules
    if "rules" not in config.get("transform", {}):
        raise ValueError("Configuration is missing 'rules' in the 'transform' section")
        
    # Validate detect section has enable flags
    detect_section = config.get("detect", {})
    if "enable_rules" not in detect_section or "enable_ml" not in detect_section:
        raise ValueError("Configuration is missing 'enable_rules' or 'enable_ml' in the 'detect' section")
        
    # Validate security section has required values
    security_section = config.get("security", {})
    if "salt" not in security_section or "date_shift_days" not in security_section:
        raise ValueError("Configuration is missing 'salt' or 'date_shift_days' in the 'security' section")


