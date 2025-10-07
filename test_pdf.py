#!/usr/bin/env python3
"""Simple script to test PDF anonymization locally."""

import sys
from pathlib import Path

from bp_ecg_etl.pdf_anonymizer import anonymize_pdf


def main():
    """Test PDF anonymization."""
    if len(sys.argv) < 2:
        print("Usage: python test_pdf.py <input.pdf> [output.pdf]")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.parent / f"{input_path.stem}_anonymized.pdf"
    
    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)
    
    print(f"📄 Input:  {input_path}")
    print(f"📄 Output: {output_path}")
    print()
    
    # Read and anonymize
    with open(input_path, "rb") as f:
        pdf_content = f.read()
    
    print("🔒 Anonymizing...")
    anonymized = anonymize_pdf(pdf_content)
    
    # Save
    with open(output_path, "wb") as f:
        f.write(anonymized)
    
    print(f"✅ Done! Output saved to {output_path}")
    print(f"📊 Size: {len(pdf_content)} → {len(anonymized)} bytes")


if __name__ == "__main__":
    main()
