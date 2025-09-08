# HIPAA De-identification Pipeline

This document outlines the enhanced de-identification pipeline for US healthcare data, designed to comply with HIPAA Safe Harbor guidelines.

## Overview

The de-identification pipeline is designed to identify and redact Protected Health Information (PHI) from medical text while preserving clinical data. It uses a modular architecture with specialized detectors for different types of identifiers.

### Key Components

1. **Modular Architecture**
   - **Stage 0**: Text normalization and OCR artifact fixing
   - **Stage 1**: Rule-based detection (Presidio)
   - **Stage 2**: ML-based detection (Hugging Face BERT)
   - **Stage 3**: Entity merging for related components
   - **Stage 4**: Overlap resolution with confidence-based voting
   - **Stage 5**: Redaction and transformation

2. **US-Specific Recognizers**
   - Enhanced MRN recognizer for US medical record number formats
   - Enhanced Fax recognizer for US fax number formats
   - US Location recognizer for US addresses and state abbreviations
   - Custom SSN recognizer for US Social Security Numbers

3. **Transformation Strategies**
   - **Redact**: Complete removal of PHI (e.g., `[REDACTED:PHONE_NUMBER]`)
   - **Hash**: Consistent hashing of identifiers (e.g., `MRN_abcdef123456`)
   - **Pseudonym**: Consistent pseudonymization (e.g., `PERSON_abcdef123456`)
   - **Generalize**: Reducing specificity (e.g., `[GENERALIZED:LOCATION]`)
   - **Date Redaction**: Complete redaction of dates for maximum security

## HIPAA Compliance

The pipeline is designed to handle all 18 HIPAA identifiers:

1. Names
2. Geographic subdivisions (locations)
3. Dates
4. Phone numbers
5. Fax numbers
6. Email addresses
7. Social Security numbers
8. Medical record numbers
9. Health plan beneficiary numbers
10. Account numbers
11. Certificate/license numbers
12. Vehicle identifiers
13. Device identifiers
14. Web URLs
15. IP addresses
16. Biometric identifiers
17. Full-face photographs
18. Any other unique identifying numbers

## Usage

### Basic Usage

```python
from hipaa_deidentifier.deidentifier_modular import HIPAADeidentifierModular

# Initialize the deidentifier
deidentifier = HIPAADeidentifierModular(
    config_path="config/defaults/base.yaml",
    spacy_model="en_core_web_lg",
    hf_model="obi/deid_bert_i2b2"
)

# Process text
result = deidentifier.deidentify("Patient John Smith, DOB 01/15/1980")

# Access de-identified text
deidentified_text = result["text"]

# Access detected entities
entities = result["entities"]
```

### Configuration

The de-identification pipeline is configured using YAML files:

- `config/defaults/base.yaml`: Default configuration for HIPAA compliance
- `config/environments/development.yaml`: Development-specific overrides
- `config/environments/production.yaml`: Production-specific overrides

Key configuration options:

```yaml
# Transformation rules for each PHI category
transform:
  default_action: "redact"
  rules:
    NAME: pseudonym
    LOCATION: generalize
    DATE: redact
    PHONE_NUMBER: redact
    # ... etc.

# Pseudonym and hash formatting
pseudonym_formats:
  DEFAULT: "{code}"
  NAME: "PERSON_{code}"
  MRN: "MRN_{code}"
  # ... etc.
```

### Environment Variables

- `HIPAA_SALT`: Salt for hashing and pseudonymization (default: "DEFAULT_SALT_REPLACE_IN_PRODUCTION")
- `HIPAA_DATE_SHIFT_DAYS`: Number of days to shift dates (default: 30)

## Performance

The de-identification pipeline has been tested on a variety of clinical notes and achieves:

- **High Recall**: Detects all 18 HIPAA identifiers with high sensitivity
- **Clinical Data Preservation**: Maintains clinical values, measurements, and medical terms
- **US-Specific Focus**: Optimized for US healthcare data formats

## Limitations

1. **State Abbreviations**: Two-letter state codes (e.g., "CA", "IL") may require pre-processing in complex contexts
2. **Partial Dates**: Some partial date formats may be detected as other entity types
3. **Context-Dependent PHI**: Some PHI may require context for accurate detection

## Best Practices

1. Always use the large spaCy model (`en_core_web_lg`) for optimal performance
2. Configure a secure salt value in production environments
3. Run comprehensive tests with your specific data formats
4. Consider post-processing for any domain-specific identifiers
5. Review de-identified output for any missed PHI before release

## Testing

The pipeline includes several test scripts:

- `test_single_note.py`: Tests de-identification on a single clinical note
- `test_all_hipaa_identifiers.py`: Tests all 18 HIPAA identifiers
- `test_final.py`: Comprehensive test with real clinical notes

Run tests to verify de-identification performance:

```bash
python test_final.py
```
