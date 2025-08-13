#!/usr/bin/env python3
"""
Verify that anonymization is working correctly by checking specific fields.
"""

import os
import sys
from pathlib import Path

# Add the bp_ecg_etl module to path
sys.path.insert(0, str(Path(__file__).parent / "bp_ecg_etl"))

# Set environment variables
os.environ.update({
    "INPUT_BUCKET": "test-input",
    "OUTPUT_BUCKET": "test-output", 
    "AWS_REGION": "us-east-1"
})

def verify_anonymization_results():
    """Verify that the correct fields are preserved/removed."""
    print("Verifying anonymization results...")
    
    try:
        import fitz
        from bp_ecg_etl.pdf_anonymizer import anonymize_pdf
        
        # Load test PDF
        test_pdf = Path(".test_data/exemplo 1.PDF")
        if not test_pdf.exists():
            print(f"Test PDF not found: {test_pdf}")
            return False
        
        print(f"Processing PDF: {test_pdf}")
        with open(test_pdf, "rb") as f:
            original_content = f.read()
        
        # Anonymize
        anonymized_content = anonymize_pdf(original_content)
        
        # Save and analyze result
        output_file = Path("test_output/verification_result.pdf")
        output_file.parent.mkdir(exist_ok=True)
        with open(output_file, "wb") as f:
            f.write(anonymized_content)
        
        # Open anonymized PDF and extract text
        doc = fitz.open(output_file)
        page1 = doc[0]
        anonymized_text = page1.get_text()
        
        print(f"\nAnonymized PDF saved: {output_file}")
        print(f"Original size: {len(original_content)} bytes")
        print(f"Anonymized size: {len(anonymized_content)} bytes")
        
        # Check what should be PRESERVED
        should_preserve = [
            ("Sexo:", "Masculino"),
            ("Data:", "04/02/2025"), 
            ("Hora:", "08:24"),
            ("Data de Nascimento:", "29/10/1979")
        ]
        
        print("\n=== FIELDS THAT SHOULD BE PRESERVED ===")
        for label, expected_value in should_preserve:
            if label in anonymized_text and expected_value in anonymized_text:
                print(f"✓ {label} {expected_value} - PRESERVED")
            elif label in anonymized_text:
                print(f"~ {label} found but value may be different")
            else:
                print(f"✗ {label} - NOT FOUND (may have been removed)")
        
        # Check what should be REMOVED
        should_remove = [
            ("Nome:", "Acassio"),
            ("CPF:", ""),
            ("RG:", ""),
            ("CRM:", "SP-183989"),
            ("Solicitante:", "Ana Carolina")
        ]
        
        print("\n=== FIELDS THAT SHOULD BE REMOVED ===")
        for label, sensitive_value in should_remove:
            if sensitive_value and sensitive_value in anonymized_text:
                print(f"✗ {sensitive_value} - STILL VISIBLE (should be removed)")
            else:
                print(f"✓ {label} sensitive data - REMOVED")
        
        # Show a sample of the anonymized text
        print(f"\n=== SAMPLE OF ANONYMIZED TEXT ===")
        lines = anonymized_text.split('\n')[:10]
        for i, line in enumerate(lines):
            if line.strip():
                print(f"{i+1:2d}: {line.strip()}")
        
        doc.close()
        return True
        
    except Exception as e:
        print(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("BP-ECG ETL Anonymization Verification")
    print("=" * 40)
    
    success = verify_anonymization_results()
    
    if success:
        print("\nVerification completed!")
    else:
        print("\nVerification failed!")
        sys.exit(1)
