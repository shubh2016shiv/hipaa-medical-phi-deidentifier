#!/usr/bin/env python3
"""
Test Configuration System

This script tests the new configuration system to ensure it works correctly.
"""
import os
import sys
import yaml
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import configuration system
from config.loader import load_config, ConfigurationError
from config.manager import ConfigManager, config


def test_load_config():
    """Test loading configuration from file."""
    print("\n" + "=" * 80)
    print("TEST: Loading Configuration")
    print("=" * 80)
    
    try:
        # Load the main configuration
        config_data = load_config("config/main.yaml")
        print("✅ Loaded main configuration")
        
        # Check required sections
        assert "detect" in config_data, "Missing 'detect' section"
        assert "transform" in config_data, "Missing 'transform' section"
        print("✅ Configuration has required sections")
        
        # Check specific values
        assert config_data["detect"]["enable_rules"] is True, "Rules should be enabled"
        assert config_data["detect"]["enable_ml"] is True, "ML should be enabled"
        print("✅ Configuration has correct values")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_environment_config():
    """Test loading environment-specific configuration."""
    print("\n" + "=" * 80)
    print("TEST: Environment-Specific Configuration")
    print("=" * 80)
    
    try:
        # Test development environment
        dev_config = load_config(environment="development")
        assert dev_config["security"]["salt"] == "DEV_SALT_DO_NOT_USE_IN_PRODUCTION"
        assert dev_config["logging"]["level"] == "DEBUG"
        print("✅ Loaded development configuration")
        
        # Test production environment
        prod_config = load_config(environment="production")
        assert prod_config["security"]["salt"] == "CHANGE_ME_IN_PRODUCTION"
        assert prod_config["logging"]["level"] == "WARNING"
        print("✅ Loaded production configuration")
        
        # Test testing environment
        test_config = load_config(environment="testing")
        assert test_config["security"]["salt"] == "TEST_SALT_CONSISTENT_FOR_TESTS"
        assert test_config["logging"]["level"] == "ERROR"
        print("✅ Loaded testing configuration")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_config_manager():
    """Test the configuration manager."""
    print("\n" + "=" * 80)
    print("TEST: Configuration Manager")
    print("=" * 80)
    
    try:
        # Reset the manager
        ConfigManager.reset()
        
        # Initialize with development environment
        ConfigManager.initialize(environment="development")
        dev_config = ConfigManager.get_config()
        assert dev_config["logging"]["level"] == "DEBUG"
        print("✅ Initialized with development environment")
        
        # Reset and initialize with production environment
        ConfigManager.reset()
        ConfigManager.initialize(environment="production")
        prod_config = ConfigManager.get_config()
        assert prod_config["logging"]["level"] == "WARNING"
        print("✅ Initialized with production environment")
        
        # Test get method with dot notation
        assert ConfigManager.get("logging.level") == "WARNING"
        assert ConfigManager.get("nonexistent.path", "default") == "default"
        print("✅ Get method works with dot notation")
        
        # Test singleton behavior
        config1 = ConfigManager()
        config2 = ConfigManager()
        assert config1 is config2, "ConfigManager should be a singleton"
        print("✅ ConfigManager is a singleton")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_config_overrides():
    """Test configuration overrides."""
    print("\n" + "=" * 80)
    print("TEST: Configuration Overrides")
    print("=" * 80)
    
    try:
        # Reset the manager
        ConfigManager.reset()
        
        # Initialize with overrides
        overrides = {
            "security": {"salt": "CUSTOM_SALT"},
            "logging": {"level": "CUSTOM_LEVEL"}
        }
        ConfigManager.initialize(overrides=overrides)
        config_data = ConfigManager.get_config()
        
        assert config_data["security"]["salt"] == "CUSTOM_SALT"
        assert config_data["logging"]["level"] == "CUSTOM_LEVEL"
        print("✅ Overrides applied correctly")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_invalid_config():
    """Test handling of invalid configuration."""
    print("\n" + "=" * 80)
    print("TEST: Invalid Configuration")
    print("=" * 80)
    
    # Create a temporary invalid configuration file
    invalid_config_path = "temp_invalid_config.yaml"
    with open(invalid_config_path, "w") as f:
        f.write("detect:\n  missing_enable_flags: true\n")
    
    try:
        # Try to load the invalid configuration
        try:
            load_config(invalid_config_path)
            print("❌ Should have raised ConfigurationError")
            return False
        except ConfigurationError:
            print("✅ Correctly raised ConfigurationError for invalid configuration")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(invalid_config_path):
            os.remove(invalid_config_path)


def main():
    """Run all tests."""
    print("CONFIGURATION SYSTEM TESTS")
    print("=========================")
    
    tests = [
        test_load_config,
        test_environment_config,
        test_config_manager,
        test_config_overrides,
        test_invalid_config
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("🎉 ALL TESTS PASSED! The configuration system is working correctly.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    return all(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
