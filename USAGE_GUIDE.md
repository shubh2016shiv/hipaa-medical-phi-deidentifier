# HIPAA De-identification Usage Guide

This guide explains how to use the HIPAA de-identification system to process patient data files.

## Quick Start

### 1. Simple File Processing

To de-identify a single file and output the result to the terminal:

```bash
python simple_deidentify.py data/patient_details.txt
```

### 2. Advanced File Processing

For more control over the de-identification process:

```bash
python deidentify_file.py data/patient_details.txt --show-entities --output-file deidentified_output.txt
```

### 3. Batch Processing

To process multiple files in a directory:

```bash
python batch_deidentify.py data/ --pattern "*.txt"
```

## Command Line Options

### simple_deidentify.py

```bash
python simple_deidentify.py <input_file_path>
```

- **input_file_path**: Path to the file containing text to de-identify
- Outputs only the de-identified text to the terminal

### deidentify_file.py

```bash
python deidentify_file.py <input_file> [options]
```

**Required Arguments:**
- **input_file**: Path to the input file

**Optional Arguments:**
- `--config`: Path to configuration file (default: config/hipaa_config.yaml)
- `--spacy-model`: spaCy model to use (default: en_core_web_md)
- `--hf-model`: Hugging Face model to use (default: dslim/bert-base-NER)
- `--device`: Device to run on (-1 for CPU, 0+ for GPU) (default: -1)
- `--show-entities`: Show detected entities along with the de-identified text
- `--output-file`: Save output to file instead of printing to terminal

**Examples:**
```bash
# Basic usage
python deidentify_file.py data/patient_details.txt

# Show detected entities
python deidentify_file.py data/patient_details.txt --show-entities

# Save to file
python deidentify_file.py data/patient_details.txt --output-file deidentified.txt

# Use custom configuration
python deidentify_file.py data/patient_details.txt --config config/policy.yaml
```

### batch_deidentify.py

```bash
python batch_deidentify.py <input_directory> [output_directory] [options]
```

**Required Arguments:**
- **input_directory**: Directory containing files to de-identify

**Optional Arguments:**
- **output_directory**: Directory to save de-identified files (default: input_dir + '_deidentified')
- `--pattern`: File pattern to match (default: *.txt)
- `--config`: Path to configuration file (default: config/hipaa_config.yaml)

**Examples:**
```bash
# Process all .txt files in data directory
python batch_deidentify.py data/

# Process specific file pattern
python batch_deidentify.py data/ --pattern "patient_*.txt"

# Specify output directory
python batch_deidentify.py data/ output/
```

## Configuration

The system uses configuration files to control de-identification behavior:

- **config/hipaa_config.yaml**: Main configuration file with all HIPAA identifiers
- **config/policy.yaml**: Simplified configuration for basic use

## Output

The de-identified text will have PHI replaced according to the configured transformation rules:

- **Names**: Replaced with pseudonyms (e.g., "John Smith" → "PATIENT_a1b2c3")
- **Dates**: Shifted by a consistent number of days
- **Phone numbers**: Replaced with "[REDACTED:PHONE_NUMBER]"
- **Email addresses**: Replaced with "[REDACTED:EMAIL_ADDRESS]"
- **Medical Record Numbers**: Replaced with hashed values (e.g., "MRN_a1b2c3d4")
- **And more...**

## Examples

### Example 1: Basic De-identification

```bash
python simple_deidentify.py data/patient_details.txt
```

Output:
```
Patient Name: PATIENT_a1b2c3
Date of Birth: 02/14/1980
Medical Record Number: MRN_d4e5f6g7
...
```

### Example 2: Show Detected Entities

```bash
python deidentify_file.py data/patient_details.txt --show-entities
```

Output:
```
Patient Name: PATIENT_a1b2c3
...

================================================================================
DETECTED ENTITIES:
================================================================================
Category: NAME
Position: 14-25
Confidence: 0.85
Text: John Smith
----------------------------------------
Category: DATE_TIME
Position: 49-59
Confidence: 0.95
Text: 01/15/1980
----------------------------------------
...
```

### Example 3: Batch Processing

```bash
python batch_deidentify.py data/ --pattern "*.txt"
```

This will:
1. Find all .txt files in the data/ directory
2. De-identify each file
3. Save the results to data_deidentified/ directory
4. Show progress for each file processed

## Troubleshooting

### Common Issues

1. **File not found**: Make sure the input file path is correct
2. **Permission denied**: Check file permissions
3. **Encoding issues**: The system uses UTF-8 encoding by default
4. **Model loading errors**: Make sure required models are installed

### Getting Help

Run any script with `--help` to see available options:

```bash
python deidentify_file.py --help
python batch_deidentify.py --help
```

