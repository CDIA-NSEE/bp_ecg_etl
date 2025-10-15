#!/usr/bin/env python3
"""Test PDF anonymization locally without Docker."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bp_ecg_etl.pdf_anonymizer import anonymize_pdf


def test_pdf_anonymization(input_path: str, output_path: str):
    """Test PDF anonymization."""
    print(f"Reading: {input_path}")
    
    with open(input_path, "rb") as f:
        pdf_content = f.read()
    
    print(f"PDF size: {len(pdf_content)} bytes")
    print("Anonymizing...")
    
    try:
        anonymized = anonymize_pdf(pdf_content)
        print(f"Anonymized size: {len(anonymized)} bytes")
        
        with open(output_path, "wb") as f:
            f.write(anonymized)
        
        print(f"Saved to: {output_path}")
        print("SUCCESS")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_anonymization.py <input.pdf> <output.pdf>")
        sys.exit(1)
    
    test_pdf_anonymization(sys.argv[1], sys.argv[2])
