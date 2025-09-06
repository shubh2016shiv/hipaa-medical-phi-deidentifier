#!/usr/bin/env python3
"""
Real Patient Data Deidentification Example

This example demonstrates the de-identification system using real patient data
from the data/patient_details.txt file, showing how the system handles
complex medical records with multiple PHI types.
"""

import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tabulate import tabulate
from hipaa_deidentifier.deidentifier import HIPAADeidentifier

def main():
    """Run real patient data deidentification example."""
    print("=" * 80)
    print("REAL PATIENT DATA DEIDENTIFICATION EXAMPLE")
    print("=" * 80)
    print("This example demonstrates de-identification of real patient data")
    print("from data/patient_details.txt, showing how the system handles")
    print("complex medical records with multiple PHI types.")
    print()
    
    try:
        # Read the real patient data
        print("Reading real patient data...")
        with open("data/patient_details.txt", "r", encoding="utf-8") as f:
            patient_text = f.read()
        print(f"✅ Loaded {len(patient_text)} characters of patient data")
        
        # Show sample of original text
        print(f"\nSAMPLE OF ORIGINAL PATIENT DATA:")
        print("-" * 80)
        print(patient_text[:500] + "...")
        print("-" * 80)
        
        # Initialize the de-identifier
        print("\nInitializing HIPAA de-identifier...")
        deidentifier = HIPAADeidentifier(
            config_path="config/main.yaml",
            spacy_model="en_core_web_md",
            hf_model="obi/deid_bert_i2b2",
            device=-1
        )
        print("✅ De-identifier initialized successfully")
        
        # De-identify the text
        print("\nProcessing patient data through ensemble pipeline...")
        result = deidentifier.deidentify(patient_text)
        print("✅ Patient data processed successfully")
        
        # Display results summary
        print(f"\nPROCESSING SUMMARY:")
        print(f"Original text length: {len(patient_text)} characters")
        print(f"De-identified text length: {len(result['text'])} characters")
        print(f"Total PHI entities detected: {len(result['entities'])}")
        
        # Count entities by category
        categories = {}
        for entity in result["entities"]:
            cat = entity["category"]
            categories[cat] = categories.get(cat, 0) + 1
        
        print(f"\nPHI CATEGORIES DETECTED:")
        print("-" * 40)
        category_table = []
        for cat, count in sorted(categories.items()):
            category_table.append([cat, count])
        
        print(tabulate(
            category_table,
            headers=["Category", "Count"],
            tablefmt="grid"
        ))
        
        # Show sample of de-identified text
        print(f"\nSAMPLE OF DE-IDENTIFIED TEXT:")
        print("-" * 80)
        print(result["text"][:500] + "...")
        print("-" * 80)
        
        # Show detailed entity information (first 20 entities)
        print(f"\nDETAILED ENTITY DETECTION (first 20 entities):")
        print("-" * 80)
        entities_table = []
        for entity in result["entities"][:20]:  # Show first 20 entities
            start_idx = max(0, entity["start"] - 10)
            end_idx = min(len(patient_text), entity["end"] + 10)
            context = f"...{patient_text[start_idx:entity['start']]}<{patient_text[entity['start']:entity['end']]}>{patient_text[entity['end']:end_idx]}..."
            
            entities_table.append([
                entity["category"],
                entity["start"],
                entity["end"],
                round(entity["confidence"], 2),
                context
            ])
        
        print(tabulate(
            entities_table,
            headers=["Category", "Start", "End", "Confidence", "Context"],
            tablefmt="grid"
        ))
        
        if len(result["entities"]) > 20:
            print(f"\n... and {len(result['entities']) - 20} more entities")
        
        # Save results
        output_file = "examples/real_patient_data_output.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Full results saved to: {output_file}")
        
        print(f"\n🎉 Real patient data deidentification example completed successfully!")
        print(f"✅ Processed complex medical record with {len(result['entities'])} PHI entities")
        print(f"✅ Detected {len(categories)} different PHI categories")
        
    except FileNotFoundError:
        print("❌ Error: data/patient_details.txt not found")
        print("Please ensure the patient data file exists in the data/ directory")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
