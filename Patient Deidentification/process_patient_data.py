#!/usr/bin/env python3
"""
HIPAA De-identification Processing Script

This script processes patient data files from the data directory using the
deidentify module to perform HIPAA-compliant de-identification.

The script automatically creates a 'deidentified_data' folder with subfolders
for each category (e.g., "Outpatient Documentation", "Emergency and Critical Care").
Each processed file generates both a JSON file and a text file in the appropriate
category subfolder.

Usage:
    python process_patient_data.py --list
        Lists all available text files in the data directory

    python process_patient_data.py <file_path>
        Processes the specified file and displays both original and de-identified text

    python process_patient_data.py <file_path> --color
        Processes the file and displays the results with colored highlighting

    python process_patient_data.py <file_path> --format json
        Processes the file and displays the results in JSON format in terminal

Output Structure:
    deidentified_data/
    ├── Outpatient Documentation/
    │   ├── progress_note_patient_01_deidentified.json
    │   └── progress_note_patient_01_deidentified.txt
    ├── Emergency and Critical Care/
    │   ├── emergency_room_note_patient_01_deidentified.json
    │   └── emergency_room_note_patient_01_deidentified.txt
    └── ...

Examples:
    python process_patient_data.py "data/patient_details.txt"
    python process_patient_data.py "data/Outpatient Documentation/progress_note_patient_01.txt" --color
    python process_patient_data.py "data/Emergency and Critical Care/emergency_room_note_patient_01.txt" --format json
"""

import os
import sys
import json
import argparse
from pathlib import Path
from tabulate import tabulate

# Import the deidentifier from deidentify.py
from hipaa_deidentifier.deidentifier_modular import HIPAADeidentifierModular
from config.config import config as global_config

def list_available_files():
    """List all available text files in the data directory."""
    data_dir = Path("data")
    files = []
    
    for root, _, filenames in os.walk(data_dir):
        for filename in filenames:
            if filename.endswith(".txt"):
                rel_path = os.path.join(os.path.relpath(root, start="."), filename)
                files.append(rel_path.replace("\\", "/"))  # Normalize path separators
    
    return sorted(files)

def get_output_paths(file_path):
    """Generate output paths for JSON and text files based on the input file path."""
    # Create deidentified_data folder if it doesn't exist
    deidentified_dir = Path("deidentified_data")
    deidentified_dir.mkdir(exist_ok=True)

    # Determine category from file path
    file_path_obj = Path(file_path)
    parts = file_path_obj.parts

    if len(parts) > 1 and parts[0] == "data":
        if len(parts) == 2:
            # File is directly in data folder (e.g., data/patient_details.txt)
            category = "General"
        else:
            # File is in a subfolder (e.g., data/Outpatient Documentation/file.txt)
            category = parts[1]
    else:
        category = "General"

    # Create category subfolder
    category_dir = deidentified_dir / category
    category_dir.mkdir(exist_ok=True)

    # Generate output filenames based on input filename
    base_name = file_path_obj.stem  # Get filename without extension
    json_file = category_dir / f"{base_name}_deidentified.json"
    text_file = category_dir / f"{base_name}_deidentified.txt"

    return json_file, text_file, category

def process_file(file_path, show_colored=False):
    """Process a single file using the deidentifier."""
    print(f"\nStarting to process file: {file_path}")

    # Get output paths
    json_output_path, text_output_path, category = get_output_paths(file_path)
    print(f"Output will be saved to: {json_output_path.parent}")
    print(f"Category: {category}")

    # Load configuration
    print("Loading configuration...")
    config_dict = global_config.get_settings()

    # Get model names from configuration
    spacy_model = config_dict.get("models", {}).get("spacy")
    hf_model = config_dict.get("models", {}).get("huggingface")
    device = config_dict.get("models", {}).get("device", -1)

    print(f"Using spaCy model: {spacy_model}")
    print(f"Using HF model: {hf_model}")
    print(f"Using device: {device}")

    # Initialize the deidentifier with the configured models
    print("Initializing deidentifier...")
    deidentifier = HIPAADeidentifierModular(
        config_path="config/main.yaml",
        spacy_model=spacy_model,
        hf_model=hf_model,
        device=device
    )

    # Read the file
    try:
        print(f"Reading file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            original_text = f.read()
        print(f"Successfully read {len(original_text)} characters")
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None, None

    # Process the text
    print("\nProcessing text...")

    # Process with or without colors
    try:
        if show_colored:
            print("Using colored output mode")
            result = deidentifier.deidentify_with_colors(original_text)
        else:
            result = deidentifier.deidentify(original_text)
        print("Processing completed successfully")

        # Save results to files
        print(f"\nSaving results to {json_output_path} and {text_output_path}")

        # Save JSON result
        with open(json_output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # Save text result
        with open(text_output_path, "w", encoding="utf-8") as f:
            f.write(result["text"])

        print(f"Results saved successfully!")

        return result, original_text
    except Exception as e:
        print(f"Error during processing: {e}")
        import traceback
        traceback.print_exc()
        return None, original_text

def display_results(result, original_text, output_format="text"):
    """Display the deidentification results in the specified format."""
    if not result:
        return

    # Display original text
    print("\n" + "="*80)
    print("ORIGINAL TEXT:")
    print("="*80)
    print(original_text)

    # Display the de-identified text
    print("\n" + "="*80)
    print("DE-IDENTIFIED TEXT:")
    print("="*80)

    if "colorized_text" in result:
        print(result["colorized_text"])
    else:
        print(result["text"])

    # Display detected entities in a table
    print("\n" + "="*80)
    print("DETECTED ENTITIES:")
    print("="*80)

    if result["entities"]:
        # Prepare table data
        table_data = []
        for entity in result["entities"]:
            table_data.append([
                entity["category"],
                f"{entity['start']}:{entity['end']}",
                f"{entity['confidence']:.3f}",
                entity.get("source", "unknown")
            ])

        # Display as table
        print(tabulate(
            table_data,
            headers=["Category", "Position", "Confidence", "Source"],
            tablefmt="grid"
        ))
        print(f"\nTotal entities detected: {len(result['entities'])}")
    else:
        print("No entities detected.")

    # Display in JSON format if requested
    if output_format == "json":
        print("\n" + "="*80)
        print("JSON OUTPUT:")
        print("="*80)
        print(json.dumps(result, ensure_ascii=False, indent=2))

def main():
    """Main function to parse arguments and process files."""
    parser = argparse.ArgumentParser(description="Process patient data files for HIPAA de-identification.")
    parser.add_argument("file", nargs="?", help="Path to the file to process (relative to project root)")
    parser.add_argument("--list", action="store_true", help="List all available files")
    parser.add_argument("--color", action="store_true", help="Show colored output for entities")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    args = parser.parse_args()

    # List available files if requested
    if args.list:
        files = list_available_files()
        print("Available files:")
        for i, file in enumerate(files, 1):
            print(f"{i}. {file}")
        return

    # If no file is specified, show usage
    if not args.file:
        parser.print_help()
        print("\nUse --list to see available files")
        return

    # Normalize file path
    file_path = args.file.replace("\\", "/")

    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return

    # Process the specified file
    result, original_text = process_file(file_path, args.color)
    if result:
        display_results(result, original_text, args.format)

if __name__ == "__main__":
    main()
