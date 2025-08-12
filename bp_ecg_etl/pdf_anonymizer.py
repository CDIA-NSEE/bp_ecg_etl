"""Simple PDF anonymization based on original main.py logic."""

import io
import fitz  # PyMuPDF
from typing import List, Tuple
from PIL import Image, ImageDraw
import structlog

from . import config

logger = structlog.get_logger(__name__)


def clamp01(v: float) -> float:
    """Clamp coordinate value to 0-1 range."""
    return max(0.0, min(1.0, float(v)))


def to_abs_rect(page: fitz.Page, rel_rect) -> fitz.Rect:
    """Convert relative coordinates to absolute rectangle."""
    x0r, y0r, x1r, y1r = [clamp01(v) for v in rel_rect]
    if x1r < x0r: x0r, x1r = x1r, x0r
    if y1r < y0r: y0r, y1r = y1r, y0r
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


def words_by_line(page) -> List[List[Tuple[float, float, float, float, str]]]:
    """Extract and group words by text lines."""
    words = page.get_text("words")  # [x0,y0,x1,y1,text,...]
    words = [w for w in words if w[4].strip()]
    words.sort(key=lambda w: (round(w[1], 1), w[0]))
    lines, current, prev_y = [], [], None
    for w in words:
        y0 = w[1]
        if prev_y is None or abs(y0 - prev_y) <= config.LINE_TOLERANCE:
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
        min(xs0) - config.PADDING, min(ys0) - config.PADDING,
        max(xs1) + config.PADDING, max(ys1) + config.PADDING
    )


def redact_line_values_after_label(page, labels_set):
    """Redact values after specific labels."""
    lines = words_by_line(page)
    for line in lines:
        texts = [w[4] for w in line]
        for i, tok in enumerate(texts):
            tok_norm = tok if tok.endswith(":") else (tok + ":")
            if tok_norm in labels_set and tok_norm not in config.KEEP_LABELS:
                start_idx = i + 1
                if start_idx >= len(line):
                    continue
                end_idx = len(line)
                for j in range(start_idx, len(texts)):
                    t_norm = texts[j] if texts[j].endswith(":") else (texts[j] + ":")
                    if t_norm in labels_set or t_norm in config.KEEP_LABELS:
                        end_idx = j
                        break
                if end_idx > start_idx:
                    page.add_redact_annot(rect_of_words(line, start_idx, end_idx), fill=(0, 0, 0))


def redact_crm_and_upper_name(page):
    """Redact CRM tokens and signature lines above them."""
    lines = words_by_line(page)
    # Redact "CRM" and everything to the right
    for line in lines:
        texts = [w[4] for w in line]
        for i, tok in enumerate(texts):
            if tok.strip() in config.CRM_TOKENS:
                page.add_redact_annot(rect_of_words(line, i, len(line)), fill=(0, 0, 0))

    # Redact the line above CRM (signature), if not a label
    crm_rects = []
    for label in config.CRM_TOKENS:
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
            if rect.y1 <= crm_r.y0 and (crm_r.y0 - rect.y1) <= config.PREVLINE_TOLERANCE:
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
    labels_set = set(config.LABELS_SAME_LINE + config.KEEP_LABELS)
    redact_line_values_after_label(page1, labels_set)
    redact_crm_and_upper_name(page1)


def anonymize_pdf(pdf_content: bytes) -> bytes:
    """Main anonymization function."""
    logger.info("Starting PDF anonymization", pdf_size=len(pdf_content))
    
    # Open PDF
    doc = fitz.open(stream=pdf_content, filetype="pdf")
    if len(doc) < 2:
        doc.close()
        raise ValueError("PDF must have at least 2 pages")
    
    try:
        # Process Page 1: Text + Coordinate redaction (preserve vector)
        page1 = doc[0]
        
        # Apply text-based redaction
        anonymize_text_on_page1(page1)
        
        # Apply coordinate-based redaction
        for coords in config.PAGE1_REDACT_COORDS:
            page1.add_redact_annot(to_abs_rect(page1, coords), fill=(0, 0, 0))
        
        # Apply all redactions and burn into images
        page1.apply_redactions(images=config.IMAGE_REDACT_MODE)
        
        # Create output PDF with page 1
        output_doc = fitz.open()
        output_doc.insert_pdf(doc, from_page=0, to_page=0)
        
        # Process Page 2: Rasterize and apply coordinate redaction
        page2 = doc[1]
        
        # Render page 2 to image
        img = render_page_to_image(page2, config.DPI_PAGE2_RENDER)
        draw = ImageDraw.Draw(img)
        b = page2.bound()
        W, H = img.size
        
        # Apply coordinate redaction to image
        for coords in config.PAGE2_REDACT_COORDS:
            r = to_abs_rect(page2, coords)
            x0 = int((r.x0 - b.x0) / b.width * W)
            y0 = int((r.y0 - b.y0) / b.height * H)
            x1 = int((r.x1 - b.x0) / b.width * W)
            y1 = int((r.y1 - b.y0) / b.height * H)
            draw.rectangle([x0, y0, x1, y1], fill=(0, 0, 0))
        
        # Convert image back to PDF page
        width, height = img.size
        page2_new = output_doc.new_page(width=width, height=height)
        
        # Save image to bytes and insert
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', optimize=True)
        img_bytes.seek(0)
        
        page2_new.insert_image(
            fitz.Rect(0, 0, width, height),
            stream=img_bytes.getvalue()
        )
        
        # Clean up metadata
        try:
            output_doc.set_metadata({})
        except Exception:
            pass  # Ignore metadata errors
        
        # Convert to bytes
        output_bytes = output_doc.tobytes(garbage=4, deflate=True)
        
        logger.info(
            "PDF anonymization completed",
            input_size=len(pdf_content),
            output_size=len(output_bytes)
        )
        
        return output_bytes
        
    finally:
        doc.close()
        output_doc.close()
