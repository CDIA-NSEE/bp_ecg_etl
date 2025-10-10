"""
Vectorial redaction for ECG page 2 using PyMuPDF.
Security level: ~85-90% (simpler, no external dependencies)
"""

import fitz
import structlog

from .config import PAGE1_REDACT_COORDS, PAGE2_REDACT_COORDS

logger = structlog.get_logger(__name__)


def extract_page2_as_png(pdf_content: bytes, dpi: int = 300) -> bytes:
    """
    Apply vectorial redactions to PDF page 2 (or page 1 if only 1 page exists).
    
    This function maintains API compatibility but now uses vectorial redaction
    instead of rasterization. Returns the complete redacted PDF, not PNG.
    
    Args:
        pdf_content: PDF file content as bytes
        dpi: DPI parameter (kept for compatibility, not used in vectorial approach)
    
    Returns:
        Complete PDF with vectorial redactions applied
    """
    logger.info("Starting vectorial redaction", pdf_size=len(pdf_content))
    
    doc = fitz.open(stream=pdf_content, filetype="pdf")
    
    try:
        page_count = len(doc)
        
        if page_count == 0:
            raise ValueError("PDF is empty (0 pages)")
        
        # Determine which page and coords to use
        if page_count >= 2:
            page_index = 1
            redact_coords = PAGE2_REDACT_COORDS
            page_label = "page_2"
        else:
            page_index = 0
            redact_coords = PAGE1_REDACT_COORDS
            page_label = "page_1"
        
        page = doc[page_index]
        page_rect = page.rect
        
        logger.debug(f"Applying {len(redact_coords)} redactions to {page_label}")
        
        # Convert relative coordinates to absolute and apply redactions
        for coords in redact_coords:
            x0_val, y0_val, x1_val, y1_val = coords
            
            # Convert from relative (0-1) to absolute coordinates
            x0 = x0_val * page_rect.width
            y0 = y0_val * page_rect.height
            x1 = x1_val * page_rect.width
            y1 = y1_val * page_rect.height
            
            rect = fitz.Rect(x0, y0, x1, y1)
            page.add_redact_annot(rect, fill=(0, 0, 0))
        
        # Apply redactions (preserva imagens fora das áreas redacted)
        page.apply_redactions()
        
        # Save with maximum security flags
        import io
        output = io.BytesIO()
        doc.save(
            output,
            garbage=4,        # Maximum garbage collection
            clean=True,       # Clean internal structure
            deflate=True,     # Compress streams
            pretty=False,     # No formatting
            linear=False,     # No linearization (removes hints)
        )
        
        sanitized_bytes = output.getvalue()
        
        logger.info(
            "Vectorial redaction completed",
            page_label=page_label,
            original_size=len(pdf_content),
            final_size=len(sanitized_bytes),
        )
        
        return sanitized_bytes
    
    finally:
        if not doc.is_closed:
            doc.close()
