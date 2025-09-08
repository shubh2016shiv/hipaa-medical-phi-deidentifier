#!/usr/bin/env python3
"""
HIPAA De-identification Tool

This script demonstrates the de-identification of Protected Health Information (PHI)
in medical text according to HIPAA Safe Harbor guidelines and the configuration.
"""

import os
import sys
import json
from hipaa_deidentifier.deidentifier_modular import HIPAADeidentifierModular

# Configuration is handled centrally without environment variables

# Sample text to de-identify
sample_text = """
Mercy River Medical Center — Outpatient Progress Note
Patient: Sarah Johnson, DOB: 03/22/1975, MRN: MR-2024-001234
Phone: (555) 987-6543, Email: sarah.johnson@email.com
Address: 123 Main St, Springfield, IL 62701
Insurance: Blue Cross Blue Shield ID: BC123456789
Chief Complaint: Chest pain and shortness of breath
Patient reports occasional dizziness in the morning.
BP 140/90, HR 88, Temp 98.6°F
Labs: A1c 7.2%, LDL 145, HDL 42
Prescribed metformin 500mg BID
"""

# Initialize the de-identifier with config file
config_path = "config/main.yaml"

# Load configuration directly
from config.config import config as global_config
config_dict = global_config.get_settings()

# Get model names from configuration
spacy_model = config_dict.get("models", {}).get("spacy")
hf_model = config_dict.get("models", {}).get("huggingface")
device = config_dict.get("models", {}).get("device", -1)

# Print what models we're using
print(f"Using spaCy model: {spacy_model}")
print(f"Using HF model: {hf_model}")

# Initialize the deidentifier with the configured models
deidentifier = HIPAADeidentifierModular(
    config_path=config_path,
    spacy_model=spacy_model,
    hf_model=hf_model,
    device=device
)

# Process the text
print(f"Processing {len(sample_text)} characters of text...")
result = deidentifier.deidentify(sample_text)

# Print the results
print("\nDe-identified text:")
print(result["text"])

print("\nDetected entities:")
for entity in result["entities"]:
    print(f"  - {entity['category']} at positions {entity['start']}:{entity['end']} (confidence: {entity['confidence']})")

# Save the results to a file
with open("deidentified_output.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("\nResults saved to deidentified_output.json")