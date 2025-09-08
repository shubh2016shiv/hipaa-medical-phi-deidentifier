#!/usr/bin/env python3
"""
Basic Deidentification Example

This example demonstrates the basic usage of the HIPAA de-identification system
with a simple medical text containing common PHI types.
"""

import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hipaa_deidentifier.deidentifier import HIPAADeidentifier

def main():
    """Run basic deidentification example."""
    print("=" * 80)
    print("BASIC DEIDENTIFICATION EXAMPLE")
    print("=" * 80)
    print("This example shows how to use the HIPAA de-identification system")
    print("with a simple medical text containing common PHI types.")
    print()
    
    # Sample medical text with common PHI
    sample_text = """
    Patient Name: John Smith
    MRN: 123456789
    Date of Birth: 01/15/1980
    Phone: (555) 123-4567
    Address: 123 Main Street, Boston, MA 02115
    Email: john.smith@example.com
    SSN: 123-45-6789
    
    Dr. Jane Doe performed a physical examination on 02/20/2023.
    Patient reports no significant changes since last visit on 12/15/2022.
    """
    
    print("ORIGINAL TEXT:")
    print("-" * 60)
    print(sample_text)
    print("-" * 60)
    
    try:
        # Initialize the de-identifier
        print("\nInitializing HIPAA de-identifier...")
        deidentifier = HIPAADeidentifier(
            config_path="config/main.yaml",
            spacy_model="en_core_web_lg",
            hf_model="obi/deid_bert_i2b2",
            device=-1
        )
        print("✅ De-identifier initialized successfully")
        
        # De-identify the text
        print("\nProcessing text through ensemble pipeline...")
        result = deidentifier.deidentify(sample_text)
        print("✅ Text processed successfully")
        
        # Display results
        print(f"\nDETECTION SUMMARY:")
        print(f"Total entities detected: {len(result['entities'])}")
        
        # Show detected entities
        print(f"\nDETECTED PHI ENTITIES:")
        print("-" * 60)
        for i, entity in enumerate(result['entities'], 1):
            print(f"{i:2d}. {entity['category']:15} | Confidence: {entity['confidence']:5.3f} | Position: {entity['start']:3d}-{entity['end']:3d}")
        
        # Show de-identified text
        print(f"\nDE-IDENTIFIED TEXT:")
        print("-" * 60)
        print(result["text"])
        print("-" * 60)
        
        # Save results
        output_file = "examples/basic_deidentification_output.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Results saved to: {output_file}")
        
        print(f"\n🎉 Basic deidentification example completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
