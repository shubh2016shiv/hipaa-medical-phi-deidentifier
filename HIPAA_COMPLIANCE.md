# HIPAA De-identification Compliance

This document outlines how the system handles all 18 HIPAA Safe Harbor identifiers to ensure proper de-identification of protected health information (PHI).

## HIPAA Safe Harbor Requirements

The HIPAA Safe Harbor method requires the removal or transformation of 18 specific identifiers:

## Implementation Overview

The system uses a hybrid approach combining rule-based patterns and machine learning to detect and transform PHI:

1. **Rule-based detection**: Uses Microsoft Presidio with custom recognizers
2. **ML-based detection**: Uses Hugging Face transformer models for NER
3. **Custom healthcare recognizers**: Specialized patterns for medical identifiers
4. **Entity merging**: Intelligent merging of overlapping entities
5. **Configurable transformations**: Different strategies for different PHI types

## HIPAA 18 Identifiers Coverage

| # | HIPAA Identifier | Detection Method | Transformation | Implementation |
|---|------------------|------------------|----------------|----------------|
| 1 | Names | ML + Rules | Pseudonym | NAME, PERSON categories |
| 2 | Geographic subdivisions | ML + Rules | Generalize | LOCATION category |
| 3 | Dates | ML + Rules | Date shifting | DATE, DATE_TIME categories |
| 4 | Phone numbers | Rules | Redact | PHONE_NUMBER category |
| 5 | Fax numbers | Rules | Redact | FAX_NUMBER category |
| 6 | Email addresses | Rules | Redact | EMAIL_ADDRESS category |
| 7 | Social Security numbers | Rules | Redact | US_SSN category |
| 8 | Medical Record numbers | Rules | Hash | MRN category |
| 9 | Health Plan IDs | Rules | Hash | HEALTH_PLAN_ID category |
| 10 | Account numbers | Rules | Hash | ACCOUNT_NUMBER category |
| 11 | Certificate/license numbers | Rules | Hash | LICENSE_NUMBER category |
| 12 | Vehicle identifiers | Rules | Redact | VEHICLE_ID category |
| 13 | Device identifiers | Rules | Hash | MEDICAL_DEVICE_ID category |
| 14 | Web URLs | Rules | Redact | URL category |
| 15 | IP addresses | Rules | Redact | IP_ADDRESS category |
| 16 | Biometric identifiers | Rules | Redact | BIOMETRIC_ID category |
| 17 | Full-face photographs | Rules | Redact | PHOTO_ID category |
| 18 | Other unique identifiers | Rules | Redact | OTHER_ID category |

## Configuration Files

The system uses two main configuration files:

### 1. `config/hipaa_config.yaml`

This is the main configuration file that defines:
- Which detection methods to enable (rule-based, ML-based)
- The list of PHI categories to detect
- Default transformation strategies
- Format templates for transformed values

### 2. `config/policy.yaml`

This file provides a simpler interface for customizing:
- Which detection methods to enable
- Transformation rules for each PHI category
- Format templates for hashed and pseudonymized values

## Custom Recognizers

The system includes custom recognizers for all 18 HIPAA identifiers:

1. `MedicalRecordNumberRecognizer`: Detects MRNs in various formats
2. `EncounterIdentifierRecognizer`: Detects encounter/visit IDs
3. `AgeOver89Recognizer`: Detects ages over 89 (HIPAA requirement)
4. `HealthPlanIDRecognizer`: Detects health plan beneficiary numbers
5. `VehicleIDRecognizer`: Detects VINs and license plates
6. `BiometricIDRecognizer`: Detects biometric identifiers
7. `PhotoIDRecognizer`: Detects photo file references
8. `OtherIDRecognizer`: Detects other unique identifiers

## Transformation Strategies

The system supports multiple transformation strategies:

1. **Redact**: Replace with `[REDACTED:CATEGORY]`
2. **Hash**: Replace with a consistent hash code
3. **Pseudonym**: Replace with a consistent pseudonym
4. **Date shifting**: Shift dates by a consistent number of days
5. **Generalization**: Reduce specificity (e.g., ZIP codes)

## Usage

To de-identify text according to HIPAA Safe Harbor:

```python
from hipaa_deidentifier.deidentifier import HIPAADeidentifier

# Initialize the de-identifier
deidentifier = HIPAADeidentifier(
    config_path="config/main.yaml",
    spacy_model="en_core_web_md",
    hf_model="obi/deid_bert_i2b2",
    device=-1
)

# De-identify text
text = "Patient: John Smith, DOB: 01/15/1980"
result = deidentifier.deidentify(text)

# Access the de-identified text
print(result["text"])
```

## Testing

The system includes comprehensive tests to verify HIPAA compliance:

- `test_hipaa_config.py`: Tests the configuration with a sample text
- `test_hipaa_18_identifiers.py`: Tests all 18 HIPAA identifiers
- `test_deidentification.py`: Basic de-identification test

