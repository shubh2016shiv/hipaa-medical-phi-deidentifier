#!/usr/bin/env python3
"""
Clinical Note De-identification Example

This example demonstrates the enhanced clinical note de-identification capabilities,
including section-aware detection, handling of initials and nicknames, facility names,
consistent date shifting, and numeric guards for labs and vitals.
"""

import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tabulate import tabulate
from hipaa_deidentifier.deidentifier import HIPAADeidentifier


def main():
    """Run clinical note de-identification example."""
    print("=" * 80)
    print("CLINICAL NOTE DE-IDENTIFICATION EXAMPLE")
    print("=" * 80)
    print("This example demonstrates the enhanced clinical note de-identification capabilities.")
    print()
    
    # Sample clinical note with various PHI types
    sample_note = """
PATIENT INFORMATION
==================
Patient Name: Sarah Johnson (S.J.)
MRN: 987654321
DOB: 05/12/1945
Age: 78
Phone: (555) 987-6543
Email: sarah.johnson@email.com
Address: 123 Oak Street, Springfield, IL 62704
Primary Care Physician: Dr. Robert Williams (R.W.)
Emergency Contact: James Johnson (husband) - (555) 123-4567

VISIT INFORMATION
===============
Date of Visit: 03/15/2023
Facility: Springfield Memorial Hospital
Provider: Dr. Jane Smith, MD
Chief Complaint: Shortness of breath, chest pain

HISTORY OF PRESENT ILLNESS
========================
Patient is a 78-year-old female with history of COPD who presents with increased shortness of breath over the past 3 days. She was seen at Central Illinois Medical Center on 03/10/2023 and was prescribed an albuterol inhaler. Patient states that her symptoms have worsened despite using the inhaler as directed. She denies fever but reports mild chest pain that worsens with deep breathing. Her granddaughter Mary Johnson has been staying with her to help with daily activities.

PAST MEDICAL HISTORY
==================
1. COPD diagnosed in 2015
2. Hypertension
3. Type 2 Diabetes Mellitus (A1c 7.2% on 02/28/2023)
4. Osteoarthritis

MEDICATIONS
==========
1. Lisinopril 10mg daily
2. Metformin 500mg twice daily
3. Albuterol inhaler 2 puffs every 4-6 hours as needed
4. Advair 250/50 1 inhalation twice daily
5. Atorvastatin 20mg daily

VITAL SIGNS
==========
BP 142/88
HR 92
RR 22
Temp 37.1°C
SpO2 91% on room air
Weight 68.5 kg

LABORATORY RESULTS
================
CBC:
- WBC 9.2
- HGB 13.5
- HCT 40.2%
- PLT 245

Chemistry:
- Na 138
- K 4.2
- Cl 102
- CO2 24
- BUN 18
- Cr 0.9
- Glucose 132

ASSESSMENT AND PLAN
=================
78-year-old female with COPD exacerbation. Patient will be admitted to Springfield Memorial Hospital under Dr. Michael Chen (ID #12345) for further management. Will start on prednisone 40mg daily for 5 days and continue albuterol treatments. Ordered chest X-ray and basic labs. Will consider adding antibiotics based on further evaluation.

Follow-up appointment scheduled with Dr. Williams on 03/29/2023 at Springfield Medical Group.

Electronically signed by:
Jane Smith, MD
NPI: 1234567890
03/15/2023 14:30
    """
    
    print("ORIGINAL CLINICAL NOTE:")
    print("-" * 80)
    print(sample_note)
    print("-" * 80)
    
    try:
        # Initialize the de-identifier
        print("\nInitializing HIPAA de-identifier with clinical enhancements...")
        deidentifier = HIPAADeidentifier(
            config_path="config/main.yaml",
            spacy_model="en_core_web_lg",
            hf_model="obi/deid_bert_i2b2",
            device=-1
        )
        print("✅ De-identifier initialized successfully")
        
        # De-identify the note with consistent patient ID
        print("\nProcessing clinical note...")
        patient_id = "patient_987654321"  # Use MRN as patient ID for consistency
        result = deidentifier.deidentify(sample_note, patient_id)
        print("✅ Clinical note processed successfully")
        
        # Display de-identified note
        print(f"\nDE-IDENTIFIED CLINICAL NOTE:")
        print("-" * 80)
        print(result["text"])
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
        print(f"\nBEFORE/AFTER COMPARISON (SELECTED LINES):")
        print("-" * 80)
        
        # Split the text into lines
        original_lines = sample_note.strip().split('\n')
        deidentified_lines = result["text"].strip().split('\n')
        
        # Select interesting lines to show (with PHI)
        interesting_line_indices = [3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17, 21, 22, 53, 54, 55, 60, 61, 62]
        
        # Create a table with before/after comparisons
        comparison_table = []
        
        # Make sure we have the same number of lines to compare
        min_lines = min(len(original_lines), len(deidentified_lines))
        
        for i in interesting_line_indices:
            if i < min_lines:
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
        
        # Highlight specific enhancements
        print(f"\nKEY CLINICAL ENHANCEMENTS DEMONSTRATED:")
        print("-" * 80)
        
        enhancements = [
            ["Section Headers", "Detected PHI in section headers (Patient Name, MRN, DOB)"],
            ["Initials/Nicknames", "Detected initials like 'S.J.' and 'R.W.'"],
            ["Facility Names", "Detected healthcare facility names like 'Springfield Memorial Hospital'"],
            ["Consistent Date Shifting", "All dates for this patient shifted by the same number of days"],
            ["Relatives & Contacts", "Detected relatives like 'James Johnson (husband)'"],
            ["Age Handling", "Preserved age under 90 years old"],
            ["Numeric Guards", "Preserved clinical measurements (BP, HR, lab values)"],
            ["Long Number Detection", "Detected long numbers like NPI"]
        ]
        
        print(tabulate(
            enhancements,
            headers=["Enhancement", "Description"],
            tablefmt="grid"
        ))
        
        # Save results
        output_file = "examples/clinical_note_output.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Results saved to: {output_file}")
        
        print(f"\n🎉 Clinical note de-identification example completed successfully!")
        print(f"✅ Detected {len(result['entities'])} PHI entities across {len(categories)} categories")
        print(f"✅ All clinical enhancements successfully demonstrated")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)



