#!/usr/bin/env python3
"""
Clinical Note De-identification Test

This example demonstrates the de-identification of a clinical note
with special attention to preserving clinical terms and medication doses.
"""

import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tabulate import tabulate
from hipaa_deidentifier.deidentifier import HIPAADeidentifier

def main():
    """Run clinical note de-identification test."""
    print("=" * 80)
    print("CLINICAL NOTE DE-IDENTIFICATION TEST")
    print("=" * 80)
    print("This example demonstrates de-identification of a clinical note")
    print("with special attention to preserving clinical terms and medication doses.")
    print()
    
    # Sample clinical note with medication doses and clinical terms
    sample_text = """
    CardioHealth University Hospital
    Discharge Summary | Admit: 02/11/2025 08:22 | Discharge: 02/18/2025 16:05
    Patient: Smith, Robert J.  (R.J. Smith)   Age: 67 yrs   DOB 1958-06-14
    MRN 000912345  |  FIN/Account: 2025-0009-ACCT  |  Medicare ID: 1EG4-TE5-MK72
    Address: 88 Westmoreland Ave., Columbus, OH 43215
    Phone 614.555.4400   Email: rjsmith@samplemail.com   SSN 912-34-5678

    Principal Diagnosis: NSTEMI -> triple-vessel disease.
    Procedure: CABG x3 on 02/13/2025 by Dr. Amelia J. Lee (License OH L-9988776).

    Hospital Course:
    Uncomplicated post-op. Temporary pacing wires removed POD#2. Small left pleural effusion resolved.

    Discharge Meds:
    - Aspirin 81 mg PO daily
    - Clopidogrel 75 mg PO daily
    - Metoprolol succinate 50 mg PO daily
    - Atorvastatin 80 mg PO nightly

    Follow-up:
    - CT surgery clinic 02/25/2025 09:00 at CardioHealth University Hospital (Suite 410).
    - PCP Dr. Michael J. Bolton in 2 weeks.

    Safety/IDs for test:
    Encounter ID: ENC-CHUH-2025-0211-001
    Health Plan Beneficiary #: HICN-CH-5566-7788
    URL: http://discharge.cardiohealth.edu/visit?id=ENC-CHUH-2025-0211-001&mrn=000912345
    IP: 10.0.25.12  |  Photo: selfie-RJ-2025-02-14.jpg
    """
    
    print("ORIGINAL CLINICAL NOTE:")
    print("-" * 80)
    print(sample_text)
    print("-" * 80)
    
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
        
        # De-identify the text with color output
        print("\nProcessing clinical note through ensemble pipeline...")
        result = deidentifier.deidentify_with_colors(sample_text)
        print("✅ Text processed successfully")
        
        # Display colorized de-identified text
        print(f"\nDE-IDENTIFIED CLINICAL NOTE (COLORIZED BY CATEGORY):")
        print("-" * 80)
        print(result["colorized_text"])
        print("-" * 80)
        
        # Count identifiers by category
        categories = {}
        for entity in result["entities"]:
            cat = entity["category"]
            categories[cat] = categories.get(cat, 0) + 1
        
        # Display category counts
        print(f"\nDETECTED PHI CATEGORIES:")
        print("-" * 40)
        category_table = []
        for cat, count in sorted(categories.items()):
            category_table.append([cat, count])
        
        print(tabulate(
            category_table,
            headers=["Category", "Count"],
            tablefmt="grid"
        ))
        
        # Create a more intuitive before/after comparison using line-by-line approach
        print(f"\nBEFORE/AFTER COMPARISON (BY LINE):")
        print("-" * 80)
        
        # Split the text into lines
        original_lines = sample_text.strip().split('\n')
        deidentified_lines = result["text"].strip().split('\n')
        
        # Create a table with before/after comparisons
        comparison_table = []
        
        # Make sure we have the same number of lines to compare
        min_lines = min(len(original_lines), len(deidentified_lines))
        
        for i in range(min_lines):
            # Skip empty lines
            if not original_lines[i].strip():
                continue
                
            comparison_table.append([
                i+1,  # Line number
                original_lines[i].strip(),
                deidentified_lines[i].strip()
            ])
        
        print(tabulate(
            comparison_table,
            headers=["Line #", "Original Text", "De-identified Text"],
            tablefmt="grid",
            maxcolwidths=[6, 35, 35]
        ))
        
        # Save results
        output_file = "examples/clinical_note_test_output.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Results saved to: {output_file}")
        
        print(f"\n🎉 Clinical note de-identification test completed successfully!")
        print(f"✅ Detected {len(result['entities'])} PHI entities across {len(categories)} categories")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
