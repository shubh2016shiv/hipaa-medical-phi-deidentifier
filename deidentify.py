#!/usr/bin/env python3
"""
HIPAA De-identification Tool

This script is the main entry point for de-identifying Protected Health Information (PHI)
in medical text according to HIPAA Safe Harbor guidelines.

Usage:
    python deidentify.py [options]

Options:
    --input FILE       Input file containing medical text (default: stdin)
    --output FILE      Output file for de-identified text (default: stdout)
    --config FILE      Configuration file path (default: config/hipaa_config.yaml)
    --spacy-model MODEL    spaCy model to use (default: en_core_web_md)
    --hf-model MODEL       Hugging Face model to use (default: obi/deid_bert_i2b2)
    --device DEVICE    Device to run on (-1 for CPU, 0+ for GPU) (default: -1)
    --verbose          Enable verbose output
    --help             Show this help message

Environment Variables:
    HIPAA_SALT              Salt for hashing identifiers
    HIPAA_DATE_SHIFT_DAYS   Number of days to shift dates

Examples:
    # Process a file
    python deidentify.py --input patient_notes.txt --output deidentified_notes.txt

    # Process from stdin to stdout
    cat patient_notes.txt | python deidentify.py > deidentified_notes.txt
"""

import os
import sys
import json
import argparse
from typing import TextIO

from hipaa_deidentifier.deidentifier import HIPAADeidentifier


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="De-identify Protected Health Information in text according to HIPAA guidelines."
    )
    
    parser.add_argument(
        "--input", 
        type=str,
        help="Input file containing medical text (default: stdin)"
    )
    
    parser.add_argument(
        "--output", 
        type=str,
        help="Output file for de-identified text (default: stdout)"
    )
    
    parser.add_argument(
        "--config", 
        type=str, 
        default="config/hipaa_config.yaml",
        help="Configuration file path (default: config/hipaa_config.yaml)"
    )
    
    parser.add_argument(
        "--spacy-model", 
        type=str, 
        default="en_core_web_md",
        help="spaCy model to use (default: en_core_web_md)"
    )
    
    parser.add_argument(
        "--hf-model", 
        type=str, 
        default="obi/deid_bert_i2b2",
        help="Hugging Face model to use (default: obi/deid_bert_i2b2)"
    )
    
    parser.add_argument(
        "--device", 
        type=int, 
        default=-1,
        help="Device to run on (-1 for CPU, 0+ for GPU) (default: -1)"
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--clear-cache", 
        action="store_true",
        help="Clear model cache before running"
    )
    
    return parser.parse_args()


def process_text(deidentifier: HIPAADeidentifier, text: str, verbose: bool = False) -> dict:
    """
    Process text through the de-identifier.
    
    Args:
        deidentifier: The HIPAADeidentifier instance
        text: Text to de-identify
        verbose: Whether to print verbose information
        
    Returns:
        Dictionary with de-identified text and entity information
    """
    if verbose:
        print(f"Processing {len(text)} characters of text...", file=sys.stderr)
        
    result = deidentifier.deidentify(text)
    
    if verbose:
        entity_count = len(result["entities"])
        print(f"Detected {entity_count} PHI entities.", file=sys.stderr)
        
    return result


def main():
    """Main entry point for the script."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Set up environment variables if not already set
    os.environ.setdefault("HIPAA_SALT", "DEFAULT_SALT_REPLACE_IN_PRODUCTION")
    os.environ.setdefault("HIPAA_DATE_SHIFT_DAYS", "30")
    
    # Clear cache if requested
    if args.clear_cache:
        from hipaa_deidentifier.phi_detection.model_cache import model_cache
        model_cache.clear_cache()
    
    # Set up input and output
    input_file = open(args.input, 'r', encoding='utf-8') if args.input else sys.stdin
    output_file = open(args.output, 'w', encoding='utf-8') if args.output else sys.stdout
    
    try:
        # Initialize the de-identifier
        if args.verbose:
            print(f"Initializing de-identifier with spaCy model: {args.spacy_model}", file=sys.stderr)
            print(f"Initializing de-identifier with HF model: {args.hf_model}", file=sys.stderr)
            
        deidentifier = HIPAADeidentifier(
            config_path=args.config,
            spacy_model=args.spacy_model,
            hf_model=args.hf_model,
            device=args.device
        )
        
        # Read input text
        text = input_file.read()
        
        # Process the text
        result = process_text(deidentifier, text, args.verbose)
        
        # Write the output
        json.dump(result, output_file, ensure_ascii=False, indent=2)
        
    finally:
        # Clean up resources
        if args.input and input_file is not sys.stdin:
            input_file.close()
            
        if args.output and output_file is not sys.stdout:
            output_file.close()


if __name__ == "__main__":
    main()
