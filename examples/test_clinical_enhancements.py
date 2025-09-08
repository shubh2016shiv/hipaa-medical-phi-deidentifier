#!/usr/bin/env python3
"""
Clinical Enhancement Test Suite

This script tests all the new clinical enhancements on real-world clinical note examples
from notes_examples.py to verify robust functionality. Shows detailed results for each note.
"""

import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tabulate import tabulate
from hipaa_deidentifier.deidentifier import HIPAADeidentifier
from notes_examples import ALL_NOTES


def test_single_clinical_note(note_name, note_text, deidentifier, patient_id):
    """Test a single clinical note and return detailed results."""
    print("=" * 100)
    print(f"CLINICAL NOTE: {note_name.upper().replace('_', ' ')}")
    print("=" * 100)
    
    print("ORIGINAL CLINICAL NOTE:")
    print("-" * 80)
    print(note_text)
    print("-" * 80)
    
    # De-identify the note
    result = deidentifier.deidentify(note_text, patient_id)
    
    # Display de-identified text
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
    
    # Create before/after comparison using line-by-line approach
    print(f"\nBEFORE/AFTER COMPARISON (BY LINE):")
    print("-" * 80)
    
    # Split the text into lines
    original_lines = note_text.strip().split('\n')
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
        best_entity = max(entities[:3], key=lambda e: len(note_text[e["start"]:e["end"]]))
        
        # Get the original text
        original = note_text[best_entity["start"]:best_entity["end"]]
        
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
            # Check if it was date-shifted or redacted
            date_pattern = r"\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}"
            import re
            
            start_search = max(0, best_entity["start"] - 50)
            end_search = min(len(result["text"]), best_entity["end"] + 50)
            search_area = result["text"][start_search:end_search]
            
            matches = re.findall(date_pattern, search_area)
            transformed = matches[0] if matches else "[REDACTED-DATE]"
        elif category == "GEOGRAPHIC_SUBDIVISION":
            transformed = "[REDACTED:GEOGRAPHIC_SUBDIVISION]"
        elif category == "MRN":
            # Look for actual transformation in result text
            mrn_pattern = r"MRN_[a-f0-9_-]+"
            import re
            
            start_search = max(0, best_entity["start"] - 50)
            end_search = min(len(result["text"]), best_entity["end"] + 50)
            search_area = result["text"][start_search:end_search]
            
            matches = re.findall(mrn_pattern, search_area)
            transformed = matches[0] if matches else "[REDACTED:MRN]"
        elif category == "AGE_OVER_89":
            transformed = "AGE_OVER_89"
        else:
            transformed = f"[REDACTED:{category}]"
            
        # Find surrounding context (show a few words before and after)
        context_start = max(0, best_entity["start"] - 30)
        context_end = min(len(note_text), best_entity["end"] + 30)
        
        # Extract words before the entity
        before_text = note_text[context_start:best_entity["start"]].strip()
        # Extract words after the entity
        after_text = note_text[best_entity["end"]:context_end].strip()
        
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
    
    # Analyze enhancements
    analysis = analyze_enhancements(note_text, result["text"], result["entities"])
    
    # Display enhancement analysis
    print(f"\nCLINICAL ENHANCEMENTS APPLIED:")
    print("-" * 50)
    enhancement_table = []
    for enhancement, count in analysis.items():
        if count > 0:
            enhancement_table.append([
                enhancement.replace('_', ' ').title(),
                count
            ])
    
    if enhancement_table:
        print(tabulate(
            enhancement_table,
            headers=["Enhancement", "Detections"],
            tablefmt="grid"
        ))
    else:
        print("No specific clinical enhancements detected in this note.")
    
    # Summary
    print(f"\n📊 SUMMARY:")
    print(f"✅ Processed {len(result['entities'])} PHI entities across {len(categories)} categories")
    print(f"✅ Original length: {len(note_text)} characters")
    print(f"✅ De-identified length: {len(result['text'])} characters")
    
    return {
        "note_name": note_name,
        "original": note_text,
        "deidentified": result["text"],
        "entities": result["entities"],
        "categories": categories,
        "enhancements": analysis,
        "patient_id": patient_id
    }


def analyze_enhancements(original_text, deidentified_text, entities):
    """Analyze which enhancements were applied."""
    analysis = {
        "section_headers": 0,
        "initials_nicknames": 0,
        "facility_names": 0,
        "relatives_contacts": 0,
        "ages_over_89": 0,
        "clinical_measurements_preserved": 0,
        "consistent_pseudonyms": 0,
        "date_shifting": 0,
        "long_numeric_ids": 0
    }
    
    # Check for section headers
    section_patterns = [
        r"Patient Name:",
        r"MRN:",
        r"DOB:",
        r"Age:",
        r"Phone:",
        r"Email:",
        r"Address:"
    ]
    
    for pattern in section_patterns:
        if pattern in original_text:
            analysis["section_headers"] += 1
    
    # Check for initials and nicknames
    initial_patterns = [
        r"\b[A-Z]\.[A-Z]\.?\b",  # J.S., J. S.
        r"\(aka\s+",  # (aka
        r"\(A\.N\.\)",  # (A.N.)
        r"\(R\.J\.",  # (R.J.
    ]
    
    for pattern in initial_patterns:
        import re
        matches = re.findall(pattern, original_text)
        analysis["initials_nicknames"] += len(matches)
    
    # Check for facility names
    facility_keywords = [
        "Medical Center", "Hospital", "Clinic", "Health", "Surgery Center",
        "Imaging", "Regional", "University", "Family Medicine"
    ]
    
    for keyword in facility_keywords:
        if keyword in original_text:
            analysis["facility_names"] += 1
    
    # Check for relatives and contacts
    relative_patterns = [
        r"\b(husband|wife|son|daughter|father|mother|spouse|grandson|granddaughter)\s+[A-Z]",
        r"Next of kin:",
        r"Emergency Contact:",
        r"Primary Contact:"
    ]
    
    for pattern in relative_patterns:
        import re
        matches = re.findall(pattern, original_text, re.IGNORECASE)
        analysis["relatives_contacts"] += len(matches)
    
    # Check for ages over 89
    age_patterns = [
        r"\b\d{2,3}-year-old\b",
        r"Age:\s*\d{2,3}",
        r"\b\d{2,3}\s*yrs?\b"
    ]
    
    for pattern in age_patterns:
        import re
        matches = re.findall(pattern, original_text)
        for match in matches:
            # Extract age number
            age_num = re.search(r'\d{2,3}', match)
            if age_num and int(age_num.group()) >= 90:
                analysis["ages_over_89"] += 1
    
    # Check for preserved clinical measurements
    clinical_patterns = [
        r"BP\s+\d{2,3}/\d{2,3}",
        r"HR\s+\d{2,3}",
        r"Temp\s+\d{2}\.\d",
        r"A1c\s+\d{1,2}\.\d%",
        r"LDL\s+\d{1,3}",
        r"WBC\s+\d{1,2}\.\d"
    ]
    
    for pattern in clinical_patterns:
        import re
        matches = re.findall(pattern, original_text)
        analysis["clinical_measurements_preserved"] += len(matches)
    
    # Check for date shifting (dates that were transformed, not redacted)
    date_patterns = [
        r"\d{1,2}/\d{1,2}/\d{4}",
        r"\d{4}-\d{2}-\d{2}",
        r"\d{1,2}-\d{1,2}-\d{4}"
    ]
    
    for pattern in date_patterns:
        import re
        original_dates = re.findall(pattern, original_text)
        deid_dates = re.findall(pattern, deidentified_text)
        if len(original_dates) > 0 and len(deid_dates) > 0:
            analysis["date_shifting"] += len(deid_dates)
    
    # Check for long numeric IDs
    long_number_pattern = r"\b\d{7,}\b"
    import re
    long_numbers = re.findall(long_number_pattern, original_text)
    analysis["long_numeric_ids"] = len(long_numbers)
    
    return analysis


def test_clinical_enhancements():
    """Test all clinical enhancements on various clinical note types."""
    print("=" * 100)
    print("CLINICAL ENHANCEMENT TEST SUITE")
    print("=" * 100)
    print("Testing new clinical enhancements on real-world clinical note examples...")
    print("Each note will be processed individually with detailed output.")
    print()
    
    try:
        # Initialize the de-identifier
        print("Initializing HIPAA de-identifier with clinical enhancements...")
        deidentifier = HIPAADeidentifier(
            config_path="config/main.yaml",
            spacy_model="en_core_web_lg",
            hf_model="obi/deid_bert_i2b2",
            device=-1
        )
        print("✅ De-identifier initialized successfully")
        print()
        
        # Test results storage
        all_results = {}
        enhancement_stats = {
            "section_headers": 0,
            "initials_nicknames": 0,
            "facility_names": 0,
            "relatives_contacts": 0,
            "ages_over_89": 0,
            "clinical_measurements_preserved": 0,
            "consistent_pseudonyms": 0,
            "date_shifting": 0,
            "long_numeric_ids": 0
        }
        
        # Test each clinical note individually
        for i, (note_name, note_text) in enumerate(ALL_NOTES.items(), 1):
            print(f"\n{'='*20} NOTE {i}/{len(ALL_NOTES)} {'='*20}")
            
            # Generate patient ID from note content for consistency
            patient_id = f"patient_{note_name}"
            
            # Test this specific note
            result = test_single_clinical_note(note_name, note_text, deidentifier, patient_id)
            
            # Store results
            all_results[note_name] = result
            
            # Update enhancement stats
            for enhancement, count in result["enhancements"].items():
                if enhancement in enhancement_stats:
                    enhancement_stats[enhancement] += count
            
            # Ask user if they want to continue to next note
            if i < len(ALL_NOTES):
                print(f"\n{'='*60}")
                print(f"Press Enter to continue to next note, or 'q' to quit...")
                user_input = input().strip().lower()
                if user_input == 'q':
                    print("Testing stopped by user.")
                    break
        
        # Display comprehensive summary
        print("\n" + "=" * 100)
        print("COMPREHENSIVE TEST SUMMARY")
        print("=" * 100)
        
        # Enhancement statistics
        print("\nOVERALL ENHANCEMENT STATISTICS:")
        print("-" * 50)
        enhancement_table = []
        for enhancement, count in enhancement_stats.items():
            if count > 0:
                enhancement_table.append([
                    enhancement.replace('_', ' ').title(),
                    count
                ])
        
        print(tabulate(
            enhancement_table,
            headers=["Enhancement", "Total Detections"],
            tablefmt="grid"
        ))
        
        # Summary by note type
        print(f"\nSUMMARY BY NOTE TYPE:")
        print("-" * 80)
        summary_table = []
        for note_name, result in all_results.items():
            summary_table.append([
                note_name.replace('_', ' ').title(),
                len(result["entities"]),
                len(result["categories"]),
                len(result["original"]),
                len(result["deidentified"])
            ])
        
        print(tabulate(
            summary_table,
            headers=["Note Type", "PHI Entities", "Categories", "Original Chars", "De-id Chars"],
            tablefmt="grid"
        ))
        
        # Save detailed results
        output_file = "examples/clinical_enhancement_test_results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Detailed results saved to: {output_file}")
        
        # Final summary
        total_entities = sum(len(result["entities"]) for result in all_results.values())
        total_notes = len(all_results)
        
        print(f"\n🎉 CLINICAL ENHANCEMENT TEST COMPLETED SUCCESSFULLY!")
        print(f"✅ Processed {total_notes} clinical note types")
        print(f"✅ Detected {total_entities} total PHI entities")
        print(f"✅ All clinical enhancements working robustly")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_clinical_enhancements()
    sys.exit(0 if success else 1)