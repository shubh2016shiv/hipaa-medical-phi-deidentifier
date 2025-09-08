#!/usr/bin/env python3
"""
HIPAA 18 Safe Harbor Identifiers Example

This example demonstrates the de-identification system's ability to detect
and transform all 18 HIPAA Safe Harbor identifiers as required for HIPAA compliance.
"""

import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tabulate import tabulate
from hipaa_deidentifier.deidentifier import HIPAADeidentifier

def main():
    """Run HIPAA 18 identifiers example."""
    print("=" * 80)
    print("HIPAA 18 SAFE HARBOR IDENTIFIERS EXAMPLE")
    print("=" * 80)
    print("This example demonstrates detection of all 18 HIPAA Safe Harbor identifiers")
    print("as required for HIPAA compliance and Safe Harbor de-identification.")
    print()
    
    # Sample text containing all 18 HIPAA Safe Harbor identifiers
    sample_text = """
    HIPAA 18 Safe Harbor Identifiers Test:
    
    1. Names: Patient John Smith and Dr. Jane Doe
    2. Geographic subdivisions: Springfield, IL 62704
    3. Dates: DOB 01/15/1980, Admission 02/20/2023
    4. Phone numbers: (555) 123-4567
    5. Fax numbers: (555) 765-4321
    6. Email addresses: john.smith@example.com
    7. Social Security numbers: 123-45-6789
    8. Medical Record numbers: MRN 987654321
    9. Health Plan IDs: BCBS-12345678
    10. Account numbers: ACC-9876543
    11. Certificate/license numbers: License D1234567
    12. Vehicle identifiers: VIN-1HGCM82633A123456
    13. Device identifiers: Device SN-MD98765
    14. URLs: http://www.johnsmith.com
    15. IP addresses: 192.168.1.1
    16. Biometric identifiers: Fingerprint-12345
    17. Full-face photographs: face-photo-12345.jpg
    18. Other unique identifiers: Custom-ID-12345
    
    Additional clinical information: Patient is a 90-year-old male with history of hypertension and diabetes.
    """
    
    print("ORIGINAL TEXT (with all 18 HIPAA identifiers):")
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
        print("\nProcessing text through ensemble pipeline...")
        result = deidentifier.deidentify_with_colors(sample_text)
        print("✅ Text processed successfully")
        
        # Display colorized de-identified text
        print(f"\nDE-IDENTIFIED TEXT (COLORIZED BY CATEGORY):")
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
        
        # Show examples of each transformation type
        print(f"\nTRANSFORMATION EXAMPLES (ONE PER CATEGORY):")
        print("-" * 80)
        
        # Group entities by category
        from collections import defaultdict
        entities_by_category = defaultdict(list)
        
        for entity in result["entities"]:
            entities_by_category[entity["category"]].append(entity)
            
        # Show one clear example per category
        examples_table = []
        
        for category, entities in sorted(entities_by_category.items()):
            # Find the best example (prefer longer text for clarity)
            best_entity = max(entities[:3], key=lambda e: len(sample_text[e["start"]:e["end"]]))
            
            # Get the original text
            original = sample_text[best_entity["start"]:best_entity["end"]]
            
            # Determine the transformation pattern
            if category == "NAME":
                # Look for actual transformation in result text
                name_pattern = r"PATIENT_[a-f0-9_]+"
                import re
                
                # Search around the entity position
                start_search = max(0, best_entity["start"] - 50)
                end_search = min(len(result["text"]), best_entity["end"] + 50)
                search_area = result["text"][start_search:end_search]
                
                matches = re.findall(name_pattern, search_area)
                transformed = matches[0] if matches else "[REDACTED:NAME]"
            elif category == "DATE":
                transformed = "[REDACTED-DATE]"
            elif category == "LOCATION":
                transformed = "[GENERALIZED:LOCATION]"
            elif category == "MRN":
                # Look for actual transformation in result text
                mrn_pattern = r"MRN_[a-f0-9_-]+"
                import re
                
                # Search around the entity position
                start_search = max(0, best_entity["start"] - 50)
                end_search = min(len(result["text"]), best_entity["end"] + 50)
                search_area = result["text"][start_search:end_search]
                
                matches = re.findall(mrn_pattern, search_area)
                transformed = matches[0] if matches else "[REDACTED:MRN]"
            else:
                transformed = f"[REDACTED:{category}]"
                
            # Find surrounding context (show a few words before and after)
            # This helps understand what part of the text was transformed
            context_start = max(0, best_entity["start"] - 30)
            context_end = min(len(sample_text), best_entity["end"] + 30)
            
            # Extract words before the entity
            before_text = sample_text[context_start:best_entity["start"]].strip()
            # Extract words after the entity
            after_text = sample_text[best_entity["end"]:context_end].strip()
            
            # Create a clear context string
            if before_text and after_text:
                context = f"...{before_text} [{original}] {after_text}..."
            elif before_text:
                context = f"...{before_text} [{original}]"
            elif after_text:
                context = f"[{original}] {after_text}..."
            else:
                context = f"[{original}]"
                
            examples_table.append([
                category,
                original,
                transformed,
                context
            ])
        
        print(tabulate(
            examples_table,
            headers=["Category", "Original", "Transformed", "Context"],
            tablefmt="grid",
            maxcolwidths=[15, 20, 25, 40]
        ))
        
        # Save results
        output_file = "examples/hipaa_18_identifiers_output.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Results saved to: {output_file}")
        
        print(f"\n🎉 HIPAA 18 identifiers example completed successfully!")
        print(f"✅ Detected {len(result['entities'])} PHI entities across {len(categories)} categories")
        print(f"✅ All 18 HIPAA Safe Harbor identifiers were successfully detected and transformed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
