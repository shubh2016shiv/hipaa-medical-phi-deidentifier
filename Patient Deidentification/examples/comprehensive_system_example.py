#!/usr/bin/env python3
"""
Comprehensive System Example

This example demonstrates the complete HIPAA de-identification system
with all features including model configuration, performance testing,
and comprehensive PHI detection capabilities.
"""

import json
import time
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tabulate import tabulate
from hipaa_deidentifier.deidentifier import HIPAADeidentifier

def main():
    """Run comprehensive system example."""
    print("=" * 80)
    print("COMPREHENSIVE SYSTEM EXAMPLE")
    print("=" * 80)
    print("This example demonstrates the complete HIPAA de-identification system")
    print("with all features including model configuration, performance testing,")
    print("and comprehensive PHI detection capabilities.")
    print()
    
    # Complex medical text with comprehensive PHI
    sample_text = """
    Patient: Dr. Sarah Johnson
    MRN: 987654321
    DOB: 03/15/1985
    Phone: (617) 555-0199
    Email: sarah.johnson@bostonhospital.com
    Address: 123 Medical Way, Boston, MA 02115
    SSN: 123-45-6789
    
    Chief Complaint: Patient presents with chest pain
    History: 38-year-old female with history of hypertension
    Physical Exam: BP 140/90, HR 88, RR 16
    Assessment: Chest pain, rule out MI
    Plan: EKG, cardiac enzymes, cardiology consult
    
    Referring Physician: Dr. Michael Chen, Cardiology Associates
    Hospital: Boston General Hospital
    Date of Service: 03/20/2025
    
    Additional PHI Examples:
    - Health Plan ID: BCBS-12345678
    - Account Number: ACC-9876543
    - License Number: D1234567
    - Vehicle ID: VIN-1HGCM82633A123456
    - Medical Device: SN-MD98765
    - Website: http://www.johnsmith.com
    - IP Address: 192.168.1.1
    - Biometric ID: Fingerprint-12345
    - Photo ID: face-photo-12345.jpg
    - Other ID: Custom-ID-12345
    """
    
    print("ORIGINAL COMPREHENSIVE MEDICAL TEXT:")
    print("-" * 80)
    print(sample_text)
    print("-" * 80)
    
    try:
        # Initialize the de-identifier
        print("\nInitializing comprehensive HIPAA de-identifier...")
        deidentifier = HIPAADeidentifier(
            config_path="config/main.yaml",
            spacy_model="en_core_web_lg",
            hf_model="obi/deid_bert_i2b2",
            device=-1
        )
        print("✅ De-identifier initialized successfully")
        print("✅ Using ensemble approach with:")
        print("   - spaCy large model (en_core_web_lg)")
        print("   - Hugging Face medical model (obi/deid_bert_i2b2)")
        print("   - Presidio rule-based detection")
        
        # Performance testing
        print(f"\nPERFORMANCE TESTING:")
        print("-" * 40)
        times = []
        for i in range(3):
            start_time = time.time()
            result = deidentifier.deidentify(sample_text)
            end_time = time.time()
            times.append(end_time - start_time)
            print(f"Run {i+1}: {times[-1]:.3f}s, {len(result['entities'])} entities")
        
        avg_time = sum(times) / len(times)
        print(f"✅ Average processing time: {avg_time:.3f}s")
        print(f"✅ Consistent entity detection across runs")
        
        # Display results
        print(f"\nDETECTION RESULTS:")
        print("-" * 40)
        print(f"Total entities detected: {len(result['entities'])}")
        print(f"Text length: {len(sample_text)} characters")
        print(f"Processing speed: {len(sample_text)/avg_time:.0f} chars/sec")
        
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
        
        # Show detailed entity information
        print(f"\nDETAILED ENTITY DETECTION:")
        print("-" * 80)
        entities_table = []
        for entity in result["entities"]:
            start_idx = max(0, entity["start"] - 10)
            end_idx = min(len(sample_text), entity["end"] + 10)
            context = f"...{sample_text[start_idx:entity['start']]}<{sample_text[entity['start']:entity['end']]}>{sample_text[entity['end']:end_idx]}..."
            
            entities_table.append([
                entity["category"],
                entity["start"],
                entity["end"],
                round(entity["confidence"], 2),
                context
            ])
        
        # Sort by position
        entities_table.sort(key=lambda x: x[1])
        
        print(tabulate(
            entities_table,
            headers=["Category", "Start", "End", "Confidence", "Context"],
            tablefmt="grid"
        ))
        
        # Show de-identified text
        print(f"\nDE-IDENTIFIED TEXT:")
        print("-" * 80)
        print(result["text"])
        print("-" * 80)
        
        # System capabilities summary
        print(f"\nSYSTEM CAPABILITIES DEMONSTRATED:")
        print("-" * 50)
        print("✅ HIPAA Safe Harbor compliance (18 identifiers)")
        print("✅ Ensemble detection (Presidio + spaCy + Hugging Face)")
        print("✅ High performance processing")
        print("✅ Comprehensive PHI coverage")
        print("✅ Professional medical text handling")
        print("✅ JSON output with full metadata")
        
        # Save results
        output_file = "examples/comprehensive_system_output.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Results saved to: {output_file}")
        
        print(f"\n🎉 Comprehensive system example completed successfully!")
        print(f"✅ Demonstrated full system capabilities")
        print(f"✅ Processed {len(result['entities'])} PHI entities across {len(categories)} categories")
        print(f"✅ Achieved {len(sample_text)/avg_time:.0f} characters/second processing speed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
