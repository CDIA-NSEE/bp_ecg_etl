"""Simple PDF anonymization based on original main.py logic."""

import io
import fitz  # PyMuPDF
from typing import List, Tuple
from PIL import Image, ImageDraw
import structlog

from .config import (
    LINE_TOLERANCE,
    PREVLINE_TOLERANCE,
    PADDING,
    LABELS_SAME_LINE,
    KEEP_LABELS,
    CRM_TOKENS,
    PAGE1_REDACT_COORDS,
    PAGE2_REDACT_COORDS,
    DPI_PAGE2_RENDER,
    IMAGE_REDACT_MODE,
)

logger = structlog.get_logger(__name__)


def clamp01(v: float) -> float:
    """Clamp coordinate value to 0-1 range."""
    return max(0.0, min(1.0, float(v)))


def to_abs_rect(page: fitz.Page, rel_rect) -> fitz.Rect:
    """Convert relative coordinates to absolute rectangle."""
    x0r, y0r, x1r, y1r = [clamp01(v) for v in rel_rect]
    if x1r < x0r:
        x0r, x1r = x1r, x0r
    if y1r < y0r:
        y0r, y1r = y1r, y0r
    b = page.bound()
    return fitz.Rect(
        b.x0 + b.width * x0r,
        b.y0 + b.height * y0r,
        b.x0 + b.width * x1r,
        b.y0 + b.height * y1r,
    )


def render_page_to_image(page: fitz.Page, dpi: int) -> Image.Image:
    """Render PDF page to PIL Image."""
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def clear_pdf_metadata(doc: fitz.Document) -> None:
    """Clear all metadata from PDF document for privacy."""
    logger.info("Clearing PDF metadata for privacy")
    
    # Get current metadata for logging
    current_metadata = doc.metadata
    if current_metadata:
        logger.debug("Current metadata", metadata_keys=list(current_metadata.keys()))
    
    # Clear all standard metadata fields using PyMuPDF's method
    metadata_to_clear = {
        'title': '',
        'author': '',
        'subject': '',
        'keywords': '',
        'creator': '',
        'producer': '',
        'creationDate': '',
        'modDate': '',
        'trapped': ''
    }
    
    # Use PyMuPDF's metadata setting method
    try:
        # Set metadata using the document's metadata property
        if doc.metadata is not None:
            for key, value in metadata_to_clear.items():
                doc.metadata[key] = value
    except Exception as e:
        logger.warning("Could not clear standard metadata", error=str(e))
    
    # Clear XMP metadata (XML-based metadata)
    try:
        # Get XMP metadata
        xmp_metadata = doc.get_xml_metadata()
        if xmp_metadata:
            logger.debug("Found XMP metadata, clearing it")
            # Set empty XMP metadata
            doc.set_xml_metadata("")
            logger.info("XMP metadata cleared successfully")
        else:
            logger.debug("No XMP metadata found")
    except Exception as e:
        logger.warning("Could not clear XMP metadata", error=str(e))
    
    # Also try to remove any custom metadata/properties
    try:
        # Clear document info dictionary if accessible
        info_dict = doc.pdf_catalog()
        if info_dict and 'Info' in info_dict:
            # Remove Info reference
            del info_dict['Info']
    except Exception as e:
        logger.warning("Could not clear extended metadata", error=str(e))
    
    # Additional cleanup: try to remove metadata streams
    try:
        # Iterate through all objects and remove metadata streams
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Remove page-level metadata if any
            try:
                page_dict = page.get_contents()
                if page_dict and isinstance(page_dict, list):
                    for content in page_dict:
                        if hasattr(content, 'metadata'):
                            content.metadata = None
            except Exception:
                pass  # Page-level metadata removal is optional
    except Exception as e:
        logger.warning("Could not clear page-level metadata", error=str(e))
    
    logger.info("PDF metadata clearing completed - standard, XMP, and extended metadata processed")


def words_by_line(page) -> List[List[Tuple[float, float, float, float, str]]]:
    """Extract and group words by text lines."""
    words = page.get_text("words")  # [x0,y0,x1,y1,text,...]
    words = [w for w in words if w[4].strip()]
    words.sort(key=lambda w: (round(w[1], 1), w[0]))
    lines, current, prev_y = [], [], None
    for w in words:
        y0 = w[1]
        if prev_y is None or abs(y0 - prev_y) <= LINE_TOLERANCE:
            current.append((w[0], w[1], w[2], w[3], w[4]))
            prev_y = y0 if prev_y is None else (prev_y + y0) / 2.0
        else:
            if current:
                lines.append(current)
            current = [(w[0], w[1], w[2], w[3], w[4])]
            prev_y = y0
    if current:
        lines.append(current)
    return lines


def rect_of_words(words_line, start_idx, end_idx) -> fitz.Rect:
    """Create rectangle from word range."""
    xs0 = [w[0] for w in words_line[start_idx:end_idx]]
    ys0 = [w[1] for w in words_line[start_idx:end_idx]]
    xs1 = [w[2] for w in words_line[start_idx:end_idx]]
    ys1 = [w[3] for w in words_line[start_idx:end_idx]]
    return fitz.Rect(
        min(xs0) - PADDING, min(ys0) - PADDING, max(xs1) + PADDING, max(ys1) + PADDING
    )


def redact_line_values_after_label(page, labels_set):
    """Redact values after specific labels - WORKING LOGIC FROM debug_redaction.py"""
    lines = words_by_line(page)
    
    for line_num, line in enumerate(lines):
        texts = [w[4] for w in line]
        
        for i, tok in enumerate(texts):
            tok_norm = tok if tok.endswith(":") else (tok + ":")
            
            if tok_norm in labels_set and tok_norm not in KEEP_LABELS:
                start_idx = i + 1
                if start_idx >= len(line):
                    continue
                
                end_idx = len(line)
                
                # Look for next label
                for j in range(start_idx, len(texts)):
                    t_norm = texts[j] if texts[j].endswith(":") else (texts[j] + ":")
                    if t_norm in labels_set or t_norm in KEEP_LABELS:
                        end_idx = j
                        break
                
                if end_idx > start_idx:
                    # Calculate rectangle and add redaction
                    rect = rect_of_words(line, start_idx, end_idx)
                    page.add_redact_annot(rect, fill=(0, 0, 0))


def redact_crm_and_upper_name(page):
    """Redact CRM tokens and signature lines above them."""
    lines = words_by_line(page)
    # Redact "CRM" and everything to the right
    for line in lines:
        texts = [w[4] for w in line]
        for i, tok in enumerate(texts):
            if tok.strip() in CRM_TOKENS:
                page.add_redact_annot(rect_of_words(line, i, len(line)), fill=(0, 0, 0))

    # Redact the line above CRM (signature), if not a label
    crm_rects = []
    for label in CRM_TOKENS:
        for r in page.search_for(label, quads=False):
            crm_rects.append(r)
    if not crm_rects:
        return
    line_rects = []
    for line in lines:
        rect = rect_of_words(line, 0, len(line))
        line_rects.append((rect, line))
    for crm_r in crm_rects:
        candidates = []
        for rect, line in line_rects:
            if rect.y1 <= crm_r.y0 and (crm_r.y0 - rect.y1) <= PREVLINE_TOLERANCE:
                if (rect.x1 > crm_r.x0 - 50) and (rect.x0 < crm_r.x1 + 50):
                    candidates.append((crm_r.y0 - rect.y1, rect, line))
        if candidates:
            candidates.sort(key=lambda t: t[0])
            _, rect, line = candidates[0]
            line_text = " ".join([w[4] for w in line])
            if ":" not in line_text:
                page.add_redact_annot(rect, fill=(0, 0, 0))


def anonymize_text_on_page1(page1: fitz.Page):
    """Apply text-based anonymization to page 1."""
    # Include ALL labels (SAME_LINE + KEEP) for proper next-label detection
    # The redaction logic will filter out KEEP_LABELS automatically
    labels_set = set(LABELS_SAME_LINE + KEEP_LABELS)
    redact_line_values_after_label(page1, labels_set)
    redact_crm_and_upper_name(page1)


def anonymize_single_page_pdf(doc: fitz.Document) -> bytes:
    """Anonymize PDF with only 1 page - WORKING LOGIC FROM debug_redaction.py"""
    logger.info("Processing single-page PDF")

    page1 = doc[0]
    
    # Apply the EXACT working logic from debug_redaction.py
    lines = words_by_line(page1)
    labels_set = set(LABELS_SAME_LINE + KEEP_LABELS)
    
    # Add text-based redactions using the working logic
    for line_num, line in enumerate(lines):
        texts = [w[4] for w in line]
        
        for i, tok in enumerate(texts):
            tok_norm = tok if tok.endswith(":") else (tok + ":")
            
            if tok_norm in labels_set and tok_norm not in KEEP_LABELS:
                start_idx = i + 1
                if start_idx >= len(line):
                    continue
                
                end_idx = len(line)
                
                # Look for next label
                for j in range(start_idx, len(texts)):
                    t_norm = texts[j] if texts[j].endswith(":") else (texts[j] + ":")
                    if t_norm in labels_set or t_norm in KEEP_LABELS:
                        end_idx = j
                        break
                
                if end_idx > start_idx:
                    # Calculate rectangle and add redaction
                    rect = rect_of_words(line, start_idx, end_idx)
                    page1.add_redact_annot(rect, fill=(0, 0, 0))
    
    # Apply CRM redactions
    redact_crm_and_upper_name(page1)

    # Apply coordinate-based redaction for page 1
    for coords in PAGE1_REDACT_COORDS:
        page1.add_redact_annot(to_abs_rect(page1, coords), fill=(0, 0, 0))

    # Apply all redactions (preserve vector format)
    page1.apply_redactions()

    # Clear PDF metadata for privacy
    clear_pdf_metadata(doc)

    # Save and return the modified PDF
    output_buffer = io.BytesIO()
    doc.save(output_buffer)

    logger.info("Single-page PDF anonymization completed")
    return output_buffer.getvalue()


def anonymize_multi_page_pdf(doc: fitz.Document) -> bytes:
    """Anonymize PDF with 2+ pages using full method (page1 + rasterized page2)."""
    logger.info("Processing multi-page PDF", pages=len(doc))

    # Process Page 1: Text + Coordinate redaction (preserve vector)
    page1 = doc[0]

    # Apply text-based redaction
    anonymize_text_on_page1(page1)

    # Apply coordinate-based redaction
    for coords in PAGE1_REDACT_COORDS:
        page1.add_redact_annot(to_abs_rect(page1, coords), fill=(0, 0, 0))

    # Apply all redactions
    page1.apply_redactions()

    # Create output PDF with page 1
    output_doc = fitz.open()
    output_doc.insert_pdf(doc, from_page=0, to_page=0)

    # Process Page 2: Rasterize and apply coordinate redaction
    page2 = doc[1]

    # Render page 2 to image
    img = render_page_to_image(page2, DPI_PAGE2_RENDER)
    draw = ImageDraw.Draw(img)

    # Apply coordinate redaction on the image
    for coords in PAGE2_REDACT_COORDS:
        # Convert relative coordinates to absolute pixel coordinates
        x1 = int(coords[0] * img.width)
        y1 = int(coords[1] * img.height)
        x2 = int(coords[2] * img.width)
        y2 = int(coords[3] * img.height)

        # Draw black rectangle
        draw.rectangle([x1, y1, x2, y2], fill=(0, 0, 0))

    # Convert image back to PDF page
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    # Create new page from image using proper method
    page2_rect = fitz.Rect(0, 0, img.width, img.height)
    new_page = output_doc.new_page(width=page2_rect.width, height=page2_rect.height)
    new_page.insert_image(page2_rect, stream=img_buffer.getvalue())

    # Clear PDF metadata for privacy
    clear_pdf_metadata(output_doc)

    # Save final PDF
    output_buffer = io.BytesIO()
    output_doc.save(output_buffer)
    output_doc.close()

    logger.info("Multi-page PDF anonymization completed")
    return output_buffer.getvalue()


def anonymize_pdf(pdf_content: bytes) -> bytes:
    """Main anonymization function with conditional logic based on page count."""
    logger.info("Starting PDF anonymization", pdf_size=len(pdf_content))

    # Open PDF
    doc = fitz.open(stream=pdf_content, filetype="pdf")
    page_count = len(doc)

    logger.info("PDF page count detected", pages=page_count)

    if page_count == 0:
        doc.close()
        raise ValueError("PDF must have at least 1 page")

    try:
        if page_count == 1:
            # Single page: use only page1 anonymization method
            return anonymize_single_page_pdf(doc)

        elif page_count >= 2:
            # Multi-page: use full method (page1 + rasterized page2)
            return anonymize_multi_page_pdf(doc)

        else:
            raise ValueError("Invalid page count")

    except Exception as e:
        logger.error("PDF anonymization failed", error=str(e), pages=page_count)
        raise

    finally:
        doc.close()
