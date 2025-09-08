# HIPAA De-identification Redaction System

This document explains the redaction capabilities of the HIPAA De-identification System and how it handles different types of Protected Health Information (PHI).

## Overview

The system uses a modular architecture to detect and redact PHI according to HIPAA Safe Harbor guidelines, which requires the removal of 18 types of identifiers. The redaction pipeline consists of:

1. **Detection**: Multiple specialized detectors identify PHI entities
2. **Redaction**: Each entity is redacted according to configurable rules
3. **Preservation**: Clinical data is preserved to maintain medical relevance

## Redaction Strategies

The system supports multiple redaction strategies that can be configured in `config/defaults/base.yaml`:

| Strategy | Description | Example |
|----------|-------------|---------|
| `redact` | Completely removes the entity and replaces it with a category label | `[REDACTED:PHONE_NUMBER]` |
| `hash` | Replaces the entity with a consistent hash value | `MRN_a1b2c3d4` |
| `pseudonym` | Replaces the entity with a consistent pseudonym | `PERSON_a1b2c3d4` |
| `generalize` | Generalizes the entity to a higher level | `ZIP code 12345 → 123XX` |
| `date_shift` | Shifts dates by a consistent amount | `01/15/2023 → 02/14/2023` |
| `preserve` | Keeps the original text (for clinical terms) | `BP 140/90` |

## HIPAA Identifiers and Handling

| # | HIPAA Identifier | Default Strategy | Notes |
|---|-----------------|------------------|-------|
| 1 | Names | `pseudonym` | Consistent pseudonyms for the same name |
| 2 | Geographic subdivisions | `generalize` | Generalizes to higher level |
| 3 | Dates | `date_shift` | Shifts by consistent days, preserves day of week |
| 4 | Phone numbers | `redact` | Complete redaction |
| 5 | Fax numbers | `redact` | Complete redaction |
| 6 | Email addresses | `redact` | Complete redaction |
| 7 | Social Security numbers | `redact` | Complete redaction |
| 8 | Medical record numbers | `hash` | Consistent hashing |
| 9 | Health plan beneficiary numbers | `hash` | Consistent hashing |
| 10 | Account numbers | `hash` | Consistent hashing |
| 11 | Certificate/license numbers | `hash` | Consistent hashing |
| 12 | Vehicle identifiers | `redact` | Complete redaction |
| 13 | Device identifiers | `hash` | Consistent hashing |
| 14 | Web URLs | `redact` | Complete redaction |
| 15 | IP addresses | `redact` | Complete redaction |
| 16 | Biometric identifiers | `redact` | Complete redaction |
| 17 | Full-face photographs | `redact` | Complete redaction |
| 18 | Any other unique identifying number | `redact` | Complete redaction |

## Special Handling

### Date Redaction
- Complete dates (MM/DD/YYYY) are shifted by a consistent number of days
- Partial dates (MM/DD or YYYY) are fully redacted
- Years alone (e.g., 1975) are redacted as `[REDACTED:YEAR]`

### MRN Redaction
- Medical Record Numbers are hashed for consistency
- Enhanced detection for various MRN formats:
  - `MR-2024-001234`
  - `MRN: 12345678`
  - `Medical Record #: 987654321`

### Clinical Data Preservation
The system preserves clinical data that is not PHI:
- Vital signs (BP, HR, Temp)
- Lab values (A1c, LDL, HDL)
- Medications and dosages
- Medical conditions and symptoms

## Configuration

Redaction strategies can be customized in `config/defaults/base.yaml`:

```yaml
transform:
  default_action: redact
  rules:
    NAME: pseudonym
    LOCATION: generalize
    DATE: date_shift
    PHONE_NUMBER: redact
    # ... other rules ...
```

## Testing

You can test the redaction capabilities using the provided test scripts:
- `test_hipaa_identifiers.py`: Tests redaction of all 18 HIPAA identifiers
- `test_mrn_redaction.py`: Tests specific MRN redaction patterns
- `test_full_redaction.py`: Tests the complete redaction pipeline

## Enhancements

Recent enhancements to the redaction system:
1. Improved date component handling to properly redact partial dates
2. Enhanced MRN detection with specialized recognizer
3. Better handling of overlapping entities
4. Consistent redaction of complex identifiers
