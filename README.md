# HIPAA De-identification Tool

A robust Python tool for de-identifying Protected Health Information (PHI) in medical text according to HIPAA Safe Harbor guidelines.

> **Note**: This project has been refactored to improve robustness, maintainability, and effectiveness. See [REFACTORING_NOTES.md](REFACTORING_NOTES.md) and [SUMMARY.md](SUMMARY.md) for details.

## Overview

This tool automatically detects and removes or transforms the 18 types of identifiers specified by HIPAA Safe Harbor, making medical text safe to use for research, analysis, or sharing while protecting patient privacy.

## HIPAA Safe Harbor Compliance

This tool handles all 18 HIPAA identifiers:

1. **Names** - Detected and pseudonymized
2. **Geographic subdivisions** - Generalized to higher level
3. **Dates** - Shifted by a consistent amount
4. **Phone numbers** - Redacted
5. **Fax numbers** - Redacted
6. **Email addresses** - Redacted
7. **Social Security numbers** - Redacted
8. **Medical Record Numbers** - Hashed
9. **Health plan beneficiary numbers** - Hashed
10. **Account numbers** - Hashed
11. **Certificate/license numbers** - Hashed
12. **Vehicle identifiers** - Redacted
13. **Device identifiers** - Hashed
14. **Web URLs** - Redacted
15. **IP addresses** - Redacted
16. **Biometric identifiers** - Redacted
17. **Full-face photographs** - Not applicable (text only)
18. **Other unique identifiers** - Detected and redacted

## Project Structure

```
hipaa-deidentifier/
├── config/
│   └── hipaa_config.yaml       # Configuration file
├── hipaa_deidentifier/         # Main package
│   ├── __init__.py
│   ├── config_loader.py        # Configuration loading
│   ├── deidentifier.py         # Main orchestrator
│   ├── models/                 # Data models
│   │   ├── __init__.py
│   │   └── phi_entity.py       # PHI entity representation
│   ├── phi_detection/          # PHI detection components
│   │   ├── __init__.py
│   │   ├── custom_recognizers.py  # Custom healthcare recognizers
│   │   ├── ml_detector.py      # ML-based detection
│   │   └── pattern_detector.py # Rule-based detection
│   ├── phi_redaction/          # PHI transformation components
│   │   ├── __init__.py
│   │   └── phi_redactor.py     # PHI redaction strategies
│   └── utils/                  # Utility functions
│       ├── __init__.py
│       ├── date_shifter.py     # Date shifting utilities
│       └── security.py         # Hashing and security
├── data/                       # Sample data
│   └── patient_details.txt     # Example patient notes
├── deidentify.py               # Main entry point script
├── requirements.txt            # Dependencies
└── README.md                   # This file
```

## Workflow

The de-identification process follows these steps:

1. **Configuration Loading**: Load settings from `config/hipaa_config.yaml`
2. **PHI Detection**: Detect PHI using multiple methods:
   - Rule-based patterns (using Microsoft Presidio)
   - Machine learning NER models (using Hugging Face Transformers)
   - Custom healthcare-specific recognizers
3. **Entity Merging**: Resolve overlapping entities from different detection methods
4. **PHI Redaction**: Apply appropriate transformations to each PHI type:
   - Redaction: Replace with `[REDACTED:TYPE]`
   - Hashing: Replace with consistent hash codes
   - Pseudonymization: Replace with consistent pseudonyms
   - Date shifting: Shift dates by a consistent number of days
   - Generalization: Reduce specificity (e.g., ZIP codes)
5. **Output**: Return de-identified text and audit information

## Setup

### Requirements

- Python 3.7+
- Dependencies listed in `requirements.txt`

### Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

2. Activate the virtual environment:
   - Windows: `.\venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Download the required models:
   ```bash
   python setup_models.py
   ```
   This will download the medium-sized spaCy model (en_core_web_md) which provides a good balance between accuracy and performance.

## Usage

### Command Line

```bash
# Basic usage (stdin to stdout)
cat data/patient_details.txt | python deidentify.py > deidentified_output.json

# Specify input and output files
python deidentify.py --input data/patient_details.txt --output deidentified_output.json

# Use a custom configuration
python deidentify.py --config my_config.yaml

# Use a different NER model
python deidentify.py --model "en_core_web_md" --device -1
```

### Environment Variables

- `HIPAA_SALT`: Salt value for hashing identifiers (default: `DEFAULT_SALT_REPLACE_IN_PRODUCTION`)
- `HIPAA_DATE_SHIFT_DAYS`: Number of days to shift dates (default: `30`)

### Python API

```python
from hipaa_deidentifier.deidentifier import HIPAADeidentifier

# Initialize the de-identifier
deidentifier = HIPAADeidentifier(
    config_path="config/main.yaml",
    spacy_model="en_core_web_md",     # spaCy model for NER
    hf_model="obi/deid_bert_i2b2",    # Optional Hugging Face model 
    device=-1                         # Use CPU (-1) or GPU (0+)
)

# De-identify text
text = "Patient: John Smith, MRN: 123456789, DOB: 01/15/1980"
result = deidentifier.deidentify(text)

# Access the de-identified text
deidentified_text = result["text"]
print(deidentified_text)
# Output: "Patient: PATIENT_a1b2, MRN: MRN_c3d4e5, DOB: 02/14/1980"

# Access detected entities
entities = result["entities"]
print(entities)
# Output: [{"start": 9, "end": 19, "category": "NAME", "confidence": 0.95}, ...]

# Quick demo with included script
# python deidentify_patient_data.py [input_file] [output_file]
```

## Configuration

The configuration file (`config/hipaa_config.yaml`) controls:

- Which detection methods to enable
- Which PHI categories to detect
- How to transform each category of PHI
- Format templates for hashed and pseudonymized values

See the comments in the configuration file for details.

## Extending the Tool

### Adding New PHI Recognizers

1. Create a new class in `hipaa_deidentifier/phi_detection/custom_recognizers.py`
2. Register the new recognizer in `hipaa_deidentifier/phi_detection/pattern_detector.py`

### Adding New Transformation Strategies

1. Add the new strategy in `hipaa_deidentifier/phi_redaction/phi_redactor.py`
2. Update the configuration file to use the new strategy

## License

[MIT License](LICENSE)