#!/usr/bin/env python3
"""Debug script to analyze PDF page 2 structure and test redactions."""

import sys
from pathlib import Path

import fitz

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bp_ecg_etl.config import PAGE2_REDACT_COORDS
from bp_ecg_etl.pdf_anonymizer import to_abs_rect


def analyze_page2(pdf_path: str):
    """Analyze page 2 structure of a PDF."""
    doc = fitz.open(pdf_path)

    if len(doc) < 2:
        print("PDF has less than 2 pages")
        return

    page2 = doc[1]

    print(f"Page 2 dimensions: {page2.rect.width} x {page2.rect.height}")
    print(f"Page 2 rotation: {page2.rotation}")
    print()

    # Extract text
    text = page2.get_text()
    print(f"Text on page 2:\n{text[:500]}")
    print()

    # Get text words with positions
    words = page2.get_text("words")
    print(f"Total words on page 2: {len(words)}")
    if words:
        print("First 10 words with positions:")
        for word in words[:10]:
            print(f"  '{word[4]}' at ({word[0]:.1f}, {word[1]:.1f})")
    print()

    # Check for images
    images = page2.get_images()
    print(f"Images on page 2: {len(images)}")
    print()

    # Show redaction coordinates
    print("Redaction areas (PAGE2_REDACT_COORDS):")
    for i, coords in enumerate(PAGE2_REDACT_COORDS):
        abs_rect = to_abs_rect(page2, coords)
        print(
            f"  {i+1}. Relative: {coords} -> Absolute: "
            f"({abs_rect.x0:.1f}, {abs_rect.y0:.1f}, {abs_rect.x1:.1f}, {abs_rect.y1:.1f})"
        )
    print()

    # Check what text is in each redaction area
    print("Text content in redaction areas:")
    for i, coords in enumerate(PAGE2_REDACT_COORDS):
        abs_rect = to_abs_rect(page2, coords)
        text_in_rect = page2.get_text("text", clip=abs_rect)
        print(f"  Area {i+1}: {repr(text_in_rect[:100])}")
    print()


def test_redaction(pdf_path: str, output_path: str):
    """Test redaction on page 2."""
    doc = fitz.open(pdf_path)

    if len(doc) < 2:
        print("PDF has less than 2 pages")
        return

    page2 = doc[1]

    print("Applying redactions to page 2...")
    for i, coords in enumerate(PAGE2_REDACT_COORDS):
        abs_rect = to_abs_rect(page2, coords)
        page2.add_redact_annot(abs_rect, fill=(0, 0, 0))
        print(f"  Added redaction {i+1}: {coords}")

    page2.apply_redactions()
    print("Redactions applied")

    doc.save(output_path, garbage=4, clean=True, deflate=True)
    print(f"Saved to: {output_path}")

    doc.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_pdf.py <pdf_path> [output_path]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "debug_output.pdf"

    print(f"Analyzing: {pdf_path}\n")
    print("=" * 80)
    analyze_page2(pdf_path)
    print("=" * 80)
    print()
    test_redaction(pdf_path, output_path)
