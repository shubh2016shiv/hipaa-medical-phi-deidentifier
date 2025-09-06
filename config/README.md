# Configuration System

This directory contains the configuration system for the HIPAA De-identification Tool. It provides a robust, hierarchical configuration system that supports different environments and overrides.

## Directory Structure

```
config/
├── __init__.py           # Package initialization
├── loader.py             # Core configuration loading functions
├── manager.py            # Singleton configuration manager
├── main.yaml             # Main configuration entry point
├── README.md             # This file
├── defaults/             # Default configurations
│   └── base.yaml         # Base configuration with common settings
└── environments/         # Environment-specific configurations
    ├── development.yaml  # Development environment settings
    ├── production.yaml   # Production environment settings
    └── testing.yaml      # Testing environment settings
```

## Usage

### Basic Usage

```python
from config.manager import config

# Get the full configuration
full_config = config.get_config()

# Get specific values using dot notation
salt = config.get("security.salt")
enable_ml = config.get("detect.enable_ml", True)  # With default value
```

### Initialization with Custom Configuration

```python
from config.manager import ConfigManager

# Initialize with specific configuration file
ConfigManager.initialize(config_path="path/to/config.yaml")

# Initialize with specific environment
ConfigManager.initialize(environment="production")

# Initialize with overrides
ConfigManager.initialize(overrides={"security": {"salt": "custom_salt"}})
```

### Configuration File Format

The configuration files use YAML format with support for imports:

```yaml
# Import other configuration files
imports:
  - defaults/base.yaml
  - environments/development.yaml

# Override specific settings
detect:
  enable_ml: true

security:
  salt: "custom_salt"
```

## Configuration Hierarchy

1. **Base Configuration** (`defaults/base.yaml`): Contains common settings
2. **Environment Configuration** (`environments/*.yaml`): Environment-specific settings
3. **Main Configuration** (`main.yaml`): Entry point that imports other configurations
4. **Runtime Overrides**: Provided programmatically

Settings from later sources override earlier ones.

## Environment Selection

The environment can be specified in three ways (in order of precedence):

1. Explicitly in code: `ConfigManager.initialize(environment="production")`
2. Environment variable: `HIPAA_ENVIRONMENT=production`
3. Default: `development`

## Required Configuration Sections

The configuration system validates that the following sections are present:

- `detect`: Detection settings
  - `enable_rules`: Whether to enable rule-based detection
  - `enable_ml`: Whether to enable ML-based detection
- `transform`: Transformation settings
  - `rules`: Rules for transforming detected entities
- `security` (optional): Security settings
  - `salt`: Salt for hashing
  - `date_shift_days`: Days to shift dates

## Best Practices

1. **Don't modify the base configuration**: Create environment-specific configurations instead
2. **Use imports for hierarchy**: Import base configurations and override as needed
3. **Use dot notation**: Access nested configuration values with `config.get("path.to.value")`
4. **Provide defaults**: Always provide default values for optional settings
5. **Initialize early**: Initialize the configuration manager at application startup
