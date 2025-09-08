#!/usr/bin/env python3
"""
Real Patient Data De-identification Demo

This script demonstrates the HIPAA de-identification system using real patient data
from the data folder. It randomly selects a patient file and processes it through
the complete de-identification pipeline.

This is a comprehensive demonstration for project visitors showing:
1. How to load real patient data
2. How to initialize the de-identification system
3. How to process text through the pipeline
4. How to view and save results

Author: HIPAA De-identification System
Version: 1.0.0
"""

import os
import sys
import json
import random
from pathlib import Path
from typing import Dict, List, Any

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hipaa_deidentifier.deidentifier_modular import HIPAADeidentifierModular


def get_random_patient_file() -> str:
    """
    Randomly select a patient file from the data directory.
    
    Returns:
        Path to a randomly selected patient file
    """
    data_dir = project_root / "data"
    
    # Get all text files from all subdirectories
    patient_files = []
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith('.txt'):
                patient_files.append(os.path.join(root, file))
    
    if not patient_files:
        raise FileNotFoundError("No patient files found in the data directory")
    
    # Randomly select a file
    selected_file = random.choice(patient_files)
    print(f"📁 Selected patient file: {os.path.relpath(selected_file, project_root)}")
    
    return selected_file


def load_patient_data(file_path: str) -> str:
    """
    Load patient data from the selected file.
    
    Args:
        file_path: Path to the patient file
        
    Returns:
        Content of the patient file
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"📄 Loaded {len(content)} characters from patient file")
        return content
        
    except Exception as e:
        print(f"❌ Error loading patient file: {str(e)}")
        raise


def initialize_deidentifier() -> HIPAADeidentifierModular:
    """
    Initialize the HIPAA de-identifier with proper configuration.
    
    Returns:
        Configured HIPAADeidentifierModular instance
    """
    print("🔧 Initializing HIPAA de-identifier...")
    
    try:
        # Initialize with default configuration
        deidentifier = HIPAADeidentifierModular(
            config_path="config/main.yaml",
            spacy_model=None,  # Use config defaults
            hf_model=None,     # Use config defaults
            device=-1          # Use CPU
        )
        
        print("✅ De-identifier initialized successfully")
        return deidentifier
        
    except Exception as e:
        print(f"❌ Error initializing de-identifier: {str(e)}")
        raise


def process_patient_data(deidentifier: HIPAADeidentifierModular, text: str) -> Dict[str, Any]:
    """
    Process patient data through the de-identification pipeline.
    
    Args:
        deidentifier: Configured de-identifier instance
        text: Patient text to process
        
    Returns:
        De-identification results
    """
    print("🔍 Processing patient data through de-identification pipeline...")
    
    try:
        # Process the text
        result = deidentifier.deidentify(text)
        
        print("✅ De-identification completed successfully")
        return result
        
    except Exception as e:
        print(f"❌ Error during de-identification: {str(e)}")
        raise


def display_results(result: Dict[str, Any], original_text: str) -> None:
    """
    Display the de-identification results in a user-friendly format.
    
    Args:
        result: De-identification results
        original_text: Original patient text
    """
    print("\n" + "=" * 80)
    print("DE-IDENTIFICATION RESULTS")
    print("=" * 80)
    
    # Basic statistics
    print(f"\n📊 Statistics:")
    print(f"   Original text length: {len(original_text):,} characters")
    print(f"   De-identified text length: {len(result['text']):,} characters")
    print(f"   PHI entities detected: {len(result['entities'])}")
    
    # Show detected entities
    if result['entities']:
        print(f"\n🔍 Detected PHI Entities:")
        entity_counts = {}
        for entity in result['entities']:
            category = entity['category']
            entity_counts[category] = entity_counts.get(category, 0) + 1
        
        for category, count in sorted(entity_counts.items()):
            print(f"   {category}: {count} entities")
        
        print(f"\n📋 Detailed Entity List:")
        for i, entity in enumerate(result['entities'], 1):
            confidence = entity.get('confidence', 0)
            print(f"   {i:2d}. {entity['category']:<15} "
                  f"pos {entity['start']:4d}-{entity['end']:4d} "
                  f"conf {confidence:.3f}")
    
    # Show text preview
    print(f"\n📝 De-identified Text Preview (first 500 characters):")
    print("-" * 60)
    preview = result['text'][:500]
    if len(result['text']) > 500:
        preview += "..."
    print(preview)
    print("-" * 60)


def save_results(result: Dict[str, Any], output_file: str) -> None:
    """
    Save the de-identification results to a file.
    
    Args:
        result: De-identification results
        output_file: Path to save the results
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Results saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error saving results: {str(e)}")


def main():
    """
    Main demonstration function.
    """
    print("🏥 HIPAA De-identification System - Real Patient Data Demo")
    print("=" * 60)
    
    try:
        # Step 1: Select a random patient file
        patient_file = get_random_patient_file()
        
        # Step 2: Load patient data
        patient_text = load_patient_data(patient_file)
        
        # Step 3: Initialize de-identifier
        deidentifier = initialize_deidentifier()
        
        # Step 4: Process the data
        result = process_patient_data(deidentifier, patient_text)
        
        # Step 5: Display results
        display_results(result, patient_text)
        
        # Step 6: Save results
        output_file = "deidentified_patient_demo_output.json"
        save_results(result, output_file)
        
        print(f"\n🎉 Demo completed successfully!")
        print(f"   Processed file: {os.path.basename(patient_file)}")
        print(f"   Output saved to: {output_file}")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

