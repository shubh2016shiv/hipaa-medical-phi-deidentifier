#!/usr/bin/env python3
"""
HIPAA Compliance Test - Verify PHI redaction across multiple clinical note examples

This script tests the de-identification pipeline against multiple clinical note examples
to ensure no HIPAA identifiers are leaked. The focus is on privacy, not accuracy.
"""

import os
import sys
import json
import re
from hipaa_deidentifier.deidentifier_modular import HIPAADeidentifierModular
from examples.notes_examples import ALL_NOTES

# HIPAA identifiers to check for leakage
HIPAA_IDENTIFIERS = {
    "NAME": [
        r'\b(?:John|Jane|Robert|Mary|William|Sarah|Michael|David|James|Linda|Jennifer|Thomas|Patricia|Richard|Susan)\s+(?:Smith|Johnson|Williams|Jones|Brown|Davis|Miller|Wilson|Moore|Taylor|Anderson|Thomas|Jackson|White|Harris)\b',  # Common full names
        r'\bDr\.\s+(?:Smith|Johnson|Williams|Jones|Brown|Davis|Miller|Wilson|Moore|Taylor|Anderson|Thomas|Jackson|White|Harris)\b',  # Doctor names with common surnames
        r'\b[A-Z]\.\s+(?:Smith|Johnson|Williams|Jones|Brown|Davis|Miller|Wilson|Moore|Taylor|Anderson|Thomas|Jackson|White|Harris)\b',  # Initials with common surnames
    ],
    "DATE": [
        r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',   # MM/DD/YYYY
        r'\b\d{4}-\d{1,2}-\d{1,2}\b',     # YYYY-MM-DD
        r'\b\d{1,2}-\d{1,2}-\d{2,4}\b',   # MM-DD-YYYY
    ],
    "PHONE": [
        r'\(\d{3}\) \d{3}-\d{4}',         # (555) 123-4567
        r'\d{3}\.\d{3}\.\d{4}',           # 555.123.4567
        r'\d{3}-\d{3}-\d{4}',             # 555-123-4567
    ],
    "SSN": [
        r'\d{3}-\d{2}-\d{4}',             # 123-45-6789
    ],
    "MRN": [
        r'MR-\d{4}-\d{6}',                # MR-2024-001234
        r'MRN-[A-Z]+-\d+-\d+',            # MRN-AZ-44-22119
    ],
    "ADDRESS": [
        r'\d+ [A-Za-z]+ (?:St|Ave|Dr|Rd|Ln|Way)',  # Street addresses
        r'[A-Za-z]+, [A-Z]{2} \d{5}',     # City, ST ZIP
    ],
    "EMAIL": [
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # Email addresses
    ],
    "URL": [
        r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^ ]*',  # URLs
    ],
    "IP": [
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b',   # IP addresses
    ]
}

def check_phi_leakage(text, phi_type, patterns):
    """Check if any PHI of the specified type is present in the text."""
    leaks = []
    
    # Common medical terms and section headers to exclude (not PHI)
    common_medical_terms = {
        "Operative Note", "Discharge Summary", "Progress Note", "Referral Letter", 
        "Patient Portal", "Secure Message", "Nursing Visit", "Service Date", 
        "Medical Group", "Diabetes Care", "Emergency Contact", "Primary Contact",
        "Address Verified", "Scanned Intake", "Visit Photos", "Post Dx", "Pre Dx",
        "Assessment Plan", "Chief Complaint", "Medical Center", "Medical Record",
        "Provider License", "Primary Care", "Outpatient Progress", "Radiology Report",
        "Triage Note", "After Visit", "Summary", "Findings", "Impression", "Technique"
    }
    
    for pattern in patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            matched_text = match.group()
            
            # Skip matches that are already redacted
            if "[REDACTED" in matched_text or "[GENERALIZED" in matched_text:
                continue
                
            # Skip matches that are hashed/pseudonymized
            if "_" in matched_text and any(prefix in matched_text for prefix in 
                                          ["PERSON_", "MRN_", "ACCT_", "HPID_", "LIC_"]):
                continue
                
            # Skip common medical terms and section headers
            if any(term in matched_text for term in common_medical_terms):
                continue
                
            # Skip date formats that are clearly not actual dates (e.g., "BP 140/90")
            if phi_type == "DATE" and ("/" in matched_text):
                if re.match(r'\d{2,3}/\d{2,3}', matched_text):  # Likely BP measurement
                    continue
                    
            leaks.append(matched_text)
    return leaks

def test_note(deidentifier, note_name, note_text):
    """Test a single clinical note for HIPAA compliance."""
    print(f"\nTesting note: {note_name}")
    print("=" * 60)
    
    # Process the note
    result = deidentifier.deidentify(note_text)
    deidentified_text = result["text"]
    
    # Save the result to a file
    output_file = f"deidentified_{note_name}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # Check for PHI leakage
    all_leaks = {}
    total_leaks = 0
    
    for phi_type, patterns in HIPAA_IDENTIFIERS.items():
        leaks = check_phi_leakage(deidentified_text, phi_type, patterns)
        if leaks:
            all_leaks[phi_type] = leaks
            total_leaks += len(leaks)
    
    # Print results
    if total_leaks > 0:
        print(f"❌ FAILED: Found {total_leaks} potential PHI leaks")
        for phi_type, leaks in all_leaks.items():
            print(f"  - {phi_type}: {', '.join(leaks)}")
    else:
        print(f"✅ PASSED: No PHI leaks detected")
    
    # Print entity stats
    entity_counts = {}
    for entity in result["entities"]:
        category = entity["category"]
        entity_counts[category] = entity_counts.get(category, 0) + 1
    
    print(f"\nDetected {len(result['entities'])} PHI entities:")
    for category, count in sorted(entity_counts.items()):
        print(f"  - {category}: {count}")
    
    print(f"\nResults saved to {output_file}")
    return total_leaks

def main():
    """Test all clinical notes for HIPAA compliance."""
    print("HIPAA COMPLIANCE TEST")
    print("=" * 60)
    
    # Initialize the deidentifier
    deidentifier = HIPAADeidentifierModular(
        config_path="config/defaults/base.yaml",
        spacy_model="en_core_web_lg",
        hf_model="obi/deid_bert_i2b2"
    )
    
    # Set environment variables
    os.environ.setdefault("HIPAA_SALT", "DEFAULT_SALT_REPLACE_IN_PRODUCTION")
    os.environ.setdefault("HIPAA_DATE_SHIFT_DAYS", "30")
    
    # Test all notes
    results = {}
    for note_name, note_text in ALL_NOTES.items():
        leaks = test_note(deidentifier, note_name, note_text)
        results[note_name] = {
            "leaks": leaks,
            "status": "PASS" if leaks == 0 else "FAIL"
        }
    
    # Print summary
    print("\nSUMMARY")
    print("=" * 60)
    
    pass_count = sum(1 for r in results.values() if r["status"] == "PASS")
    fail_count = len(results) - pass_count
    
    print(f"Total notes tested: {len(results)}")
    print(f"Passed: {pass_count}")
    print(f"Failed: {fail_count}")
    
    if fail_count > 0:
        print("\nFailed notes:")
        for note_name, result in results.items():
            if result["status"] == "FAIL":
                print(f"  - {note_name}: {result['leaks']} potential leaks")
    
    # Save overall results
    with open("hipaa_compliance_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\nResults saved to hipaa_compliance_results.json")
    
    # Return exit code based on results
    return 1 if fail_count > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
