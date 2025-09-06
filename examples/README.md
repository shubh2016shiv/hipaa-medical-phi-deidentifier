# HIPAA De-identification System Examples

This directory contains working examples that demonstrate the capabilities of the HIPAA de-identification system. Each example shows real usage of the pipeline with actual input data and produces real output.

## Available Examples

### 1. Basic Deidentification Example
**File:** `basic_deidentification_example.py`
- Demonstrates basic usage with simple medical text
- Shows common PHI types (names, MRN, dates, phone, email, SSN)
- Perfect for getting started with the system

### 2. HIPAA 18 Identifiers Example
**File:** `hipaa_18_identifiers_example.py`
- Demonstrates detection of all 18 HIPAA Safe Harbor identifiers
- Shows comprehensive PHI coverage for HIPAA compliance
- Includes detailed entity analysis and categorization

### 3. Real Patient Data Example
**File:** `real_patient_data_example.py`
- Uses actual patient data from `data/patient_details.txt`
- Shows how the system handles complex medical records
- Demonstrates real-world usage scenarios

### 4. Ensemble Pipeline Example
**File:** `ensemble_pipeline_example.py`
- Demonstrates the three-component ensemble approach
- Shows how Presidio, spaCy, and Hugging Face work together
- Illustrates the benefits of the ensemble approach

### 5. Comprehensive System Example
**File:** `comprehensive_system_example.py`
- Shows complete system capabilities
- Includes performance testing and analysis
- Demonstrates professional medical text processing

## Running the Examples

Each example can be run independently:

```bash
# Basic example
python examples/basic_deidentification_example.py

# HIPAA 18 identifiers
python examples/hipaa_18_identifiers_example.py

# Real patient data
python examples/real_patient_data_example.py

# Ensemble pipeline
python examples/ensemble_pipeline_example.py

# Comprehensive system
python examples/comprehensive_system_example.py
```

## Output Files

Each example generates a JSON output file with:
- De-identified text
- Detected PHI entities with metadata
- Confidence scores and positions
- Processing statistics

## Key Features Demonstrated

- **Three-Component Ensemble**: Presidio (rules) + spaCy (general NER) + Hugging Face (medical PHI)
- **HIPAA Compliance**: All 18 Safe Harbor identifiers supported
- **High Performance**: Fast processing with consistent results
- **Professional Output**: JSON format with comprehensive metadata
- **Real Data Processing**: Works with actual medical records

## Requirements

- Python 3.8+
- All dependencies from `requirements.txt`
- spaCy medium model (`en_core_web_md`)
- Hugging Face medical model (`obi/deid_bert_i2b2`)

## Notes

- All examples use real input data and produce real output
- No mocking or simulated data
- Examples demonstrate actual pipeline stages and components
- Output files are saved in the `examples/` directory
