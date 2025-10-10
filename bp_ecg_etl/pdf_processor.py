"""
PDF processing pipeline using VECTORIAL redaction (PyMuPDF + Ghostscript).
"""

import fitz
import structlog

from .config import DPI_PAGE2_RENDER
from .ecg_extractor import extract_page2_as_png
from .pdf_anonymizer import anonymize_pdf

logger = structlog.get_logger(__name__)


def process_complete_pdf(pdf_content: bytes, dpi: int = DPI_PAGE2_RENDER) -> bytes:
    """
    Process PDF with VECTORIAL redaction pipeline.
    
    Pipeline:
    1. Página 1: Anonimização de texto (removes sensitive text)
    2. Página 2: Redação vetorial com PyMuPDF + Ghostscript
    
    Args:
        pdf_content: Original PDF content as bytes
        dpi: DPI parameter (kept for compatibility, not used in vectorial approach)
    
    Returns:
        Final PDF with vectorial redactions as bytes
    
    Raises:
        ValueError: If PDF has 0 pages
        RuntimeError: If Ghostscript is not installed
        Exception: If processing fails
    """
    logger.info("Starting PDF processing (VECTORIAL)", pdf_size=len(pdf_content))
    
    doc = fitz.open(stream=pdf_content, filetype="pdf")
    
    try:
        page_count = len(doc)
        
        if page_count == 0:
            raise ValueError("PDF is empty (0 pages)")
        
        doc.close()
        
        # === CASO 1: PDF com 1 página ===
        if page_count == 1:
            logger.info("PDF has 1 page, applying text anonymization + vectorial redaction")
            
            # Step 1: Anonymize text on page 1
            anonymized_pdf = anonymize_pdf(pdf_content)
            
            # Step 2: Apply vectorial redactions to page 1
            final_pdf = extract_page2_as_png(anonymized_pdf, dpi)
            
            logger.info(
                "Single-page PDF processed",
                original_size=len(pdf_content),
                final_size=len(final_pdf),
                method="vectorial",
            )
            
            return final_pdf
        
        # === CASO 2: PDF com 2+ páginas ===
        logger.info("PDF has 2+ pages, applying full vectorial pipeline")
        
        # Step 1: Anonymize text on page 1
        logger.debug("Step 1: Anonymizing page 1 (text)")
        anonymized_pdf = anonymize_pdf(pdf_content)
        
        # Step 2: Apply vectorial redactions to page 2
        logger.debug("Step 2: Applying vectorial redactions to page 2")
        final_pdf = extract_page2_as_png(anonymized_pdf, dpi)
        
        logger.info(
            "Multi-page PDF processed",
            original_size=len(pdf_content),
            anonymized_size=len(anonymized_pdf),
            final_size=len(final_pdf),
            method="vectorial",
        )
        
        return final_pdf
    
    except Exception as e:
        logger.error(
            "PDF processing failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise
    
    finally:
        if not doc.is_closed:
            doc.close()
