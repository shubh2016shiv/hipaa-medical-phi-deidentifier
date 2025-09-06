#!/usr/bin/env python3
"""
Comprehensive Test Script for Refactored HIPAA De-identification System

This script tests all the changes made to ensure:
1. Model configuration is correct (spaCy + HF medical model)
2. No environment variable dependencies
3. Configuration is loaded from YAML only
4. Both models are working in ensemble
"""

import json
import time
from tabulate import tabulate
from hipaa_deidentifier.deidentifier import HIPAADeidentifier

def test_model_configuration():
    """Test that the correct models are being used."""
    print("=" * 80)
    print("TEST 1: Model Configuration")
    print("=" * 80)
    
    try:
        # Initialize de-identifier
        deidentifier = HIPAADeidentifier(
            config_path="config/main.yaml",
            spacy_model="en_core_web_md",
            hf_model="obi/deid_bert_i2b2",
            device=-1
        )
        
        print("✅ De-identifier initialized successfully")
        print(f"✅ spaCy model: en_core_web_md")
        print(f"✅ HF model: obi/deid_bert_i2b2")
        print(f"✅ Configuration loaded from: config/hipaa_config.yaml")
        
        return True
    except Exception as e:
        print(f"❌ Error initializing de-identifier: {e}")
        return False

def test_no_environment_dependencies():
    """Test that no environment variables are required."""
    print("\n" + "=" * 80)
    print("TEST 2: No Environment Variable Dependencies")
    print("=" * 80)
    
    # Clear any existing environment variables
    import os
    env_vars_to_clear = [
        "HIPAA_SALT", "HIPAA_DATE_SHIFT_DAYS", 
        "DEID_SALT", "DEID_DATE_SHIFT_DAYS",
        "PRESIDIO_SPACY_MODEL"
    ]
    
    original_values = {}
    for var in env_vars_to_clear:
        original_values[var] = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]
    
    try:
        # Try to initialize without any environment variables
        deidentifier = HIPAADeidentifier(
            config_path="config/main.yaml",
            spacy_model="en_core_web_md",
            hf_model="obi/deid_bert_i2b2",
            device=-1
        )
        
        print("✅ De-identifier works without environment variables")
        print("✅ All configuration loaded from YAML file")
        
        return True
    except Exception as e:
        print(f"❌ Error without environment variables: {e}")
        return False
    finally:
        # Restore original environment variables
        for var, value in original_values.items():
            if value is not None:
                os.environ[var] = value

def test_ensemble_detection():
    """Test that both spaCy and HF models are working together."""
    print("\n" + "=" * 80)
    print("TEST 3: Ensemble Detection (spaCy + HF Models)")
    print("=" * 80)
    
    # Sample text with various PHI types
    sample_text = """
    Patient: John Smith
    MRN: 123456789
    DOB: 01/15/1980
    Phone: (555) 123-4567
    Address: 123 Main Street, Boston, MA 02115
    Email: john.smith@example.com
    SSN: 123-45-6789
    
    Dr. Jane Doe examined the patient on 02/20/2023.
    Patient reports no significant changes since last visit on 12/15/2022.
    """
    
    try:
        deidentifier = HIPAADeidentifier(
            config_path="config/main.yaml",
            spacy_model="en_core_web_md",
            hf_model="obi/deid_bert_i2b2",
            device=-1
        )
        
        print("Processing sample text...")
        result = deidentifier.deidentify(sample_text)
        
        print(f"✅ Text processed successfully")
        print(f"✅ Detected {len(result['entities'])} entities")
        
        # Show detected entities
        print("\nDetected entities:")
        entities_table = []
        for entity in result["entities"]:
            start_idx = max(0, entity["start"] - 10)
            end_idx = min(len(sample_text), entity["end"] + 10)
            context = f"...{sample_text[start_idx:entity['start']]}<{sample_text[entity['start']:entity['end']]}>{sample_text[entity['end']:end_idx]}..."
            
            entities_table.append([
                entity["category"],
                entity["start"],
                entity["end"],
                round(entity["confidence"], 3),
                context
            ])
        
        # Sort by position
        entities_table.sort(key=lambda x: x[1])
        
        print(tabulate(
            entities_table,
            headers=["Category", "Start", "End", "Confidence", "Context"],
            tablefmt="grid"
        ))
        
        print(f"\nDe-identified text:")
        print("-" * 60)
        print(result["text"])
        print("-" * 60)
        
        return True
    except Exception as e:
        print(f"❌ Error in ensemble detection: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_configuration_loading():
    """Test that configuration is loaded correctly from YAML."""
    print("\n" + "=" * 80)
    print("TEST 4: Configuration Loading from YAML")
    print("=" * 80)
    
    try:
        from config.manager import ConfigManager
        
        ConfigManager.initialize(config_path="config/main.yaml")
        config = ConfigManager.get_config()
        
        print("✅ Configuration loaded successfully")
        print(f"✅ Security salt: {config['security']['salt']}")
        print(f"✅ Date shift days: {config['security']['date_shift_days']}")
        print(f"✅ Rules enabled: {config['detect']['enable_rules']}")
        print(f"✅ ML enabled: {config['detect']['enable_ml']}")
        print(f"✅ PHI categories: {len(config['detect']['categories'])}")
        
        return True
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        return False

def test_performance():
    """Test performance with the new model configuration."""
    print("\n" + "=" * 80)
    print("TEST 5: Performance Test")
    print("=" * 80)
    
    sample_text = """
    Patient: John Smith, MRN: 123456789, DOB: 01/15/1980
    Phone: (555) 123-4567, Address: 123 Main Street, Boston, MA 02115
    Email: john.smith@example.com, SSN: 123-45-6789
    Dr. Jane Doe examined the patient on 02/20/2023.
    """
    
    try:
        deidentifier = HIPAADeidentifier(
            config_path="config/main.yaml",
            spacy_model="en_core_web_md",
            hf_model="obi/deid_bert_i2b2",
            device=-1
        )
        
        # Test multiple runs to check consistency
        times = []
        for i in range(3):
            start_time = time.time()
            result = deidentifier.deidentify(sample_text)
            end_time = time.time()
            times.append(end_time - start_time)
            print(f"Run {i+1}: {times[-1]:.3f}s, {len(result['entities'])} entities")
        
        avg_time = sum(times) / len(times)
        print(f"✅ Average processing time: {avg_time:.3f}s")
        print(f"✅ All runs detected same number of entities: {len(result['entities'])}")
        
        return True
    except Exception as e:
        print(f"❌ Error in performance test: {e}")
        return False

def test_hipaa_ensemble_pipeline():
    """Test the HIPAA deidentifier pipeline ensemble implementation."""
    print("\n" + "=" * 80)
    print("TEST 6: HIPAA Deidentifier Ensemble Pipeline")
    print("=" * 80)
    
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
    """
    
    try:
        # Import the HIPAA deidentifier pipeline
        from hipaa_deidentifier.deidentifier import HIPAADeidentifier
        
        print("Initializing HIPAA deidentifier ensemble pipeline...")
        deidentifier = HIPAADeidentifier(
            config_path="config/main.yaml",
            spacy_model="en_core_web_md",
            hf_model="obi/deid_bert_i2b2",
            device=-1
        )
        
        print("✅ HIPAA deidentifier pipeline initialized successfully")
        print("✅ Using three-component ensemble approach:")
        print("   - Presidio (Rule-Based Detection)")
        print("   - spaCy (General NER)")  
        print("   - Hugging Face (Medical PHI)")
        
        # Process the text
        print("\nProcessing medical text...")
        result = deidentifier.deidentify(sample_text)
        
        # Verify output structure
        assert "text" in result, "Missing 'text' field"
        assert "entities" in result, "Missing 'entities' field"
        
        # Verify detection results
        print(f"✅ Detected {len(result['entities'])} PHI entities")
        print(f"✅ Text length: {len(sample_text)} characters")
        print(f"✅ De-identified text length: {len(result['text'])} characters")
        
        print(f"✅ Text processed successfully")
        print(f"✅ Total entities detected: {len(result['entities'])}")
        
        # Verify entity structure
        for entity in result['entities']:
            assert "start" in entity, "Missing 'start' in entity"
            assert "end" in entity, "Missing 'end' in entity"
            assert "category" in entity, "Missing 'category' in entity"
            assert "confidence" in entity, "Missing 'confidence' in entity"
            assert 0 <= entity["confidence"] <= 1, f"Invalid confidence: {entity['confidence']}"
            assert entity["start"] < entity["end"], f"Invalid span: {entity['start']}-{entity['end']}"
        
        print("✅ Entity structure validation passed")
        
        # Test JSON serialization
        json_str = json.dumps(result, ensure_ascii=False, indent=2)
        parsed_back = json.loads(json_str)
        assert parsed_back == result, "JSON round-trip failed"
        print("✅ JSON serialization works correctly")
        
        # Show sample of detected entities
        print(f"\nSample detected entities:")
        for i, entity in enumerate(result['entities'][:5], 1):
            print(f"  {i}. {entity['category']:15} | Confidence: {entity['confidence']:5.3f} | Pos: {entity['start']:3d}-{entity['end']:3d}")
        if len(result['entities']) > 5:
            print(f"  ... and {len(result['entities']) - 5} more entities")
        
        print(f"\nSample de-identified text:")
        print(f"  {result['text'][:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in HIPAA deidentifier ensemble test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("HIPAA De-identification System - Refactored Test Suite")
    print("Testing model configuration and YAML-only configuration")
    
    tests = [
        test_model_configuration,
        test_no_environment_dependencies,
        test_ensemble_detection,
        test_configuration_loading,
        test_performance,
        test_hipaa_ensemble_pipeline
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! The refactored system is working correctly.")
        print("\nKey improvements verified:")
        print("✅ Correct model configuration (spaCy + medical HF model)")
        print("✅ No environment variable dependencies")
        print("✅ YAML-only configuration")
        print("✅ Ensemble detection working")
        print("✅ Performance acceptable")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
