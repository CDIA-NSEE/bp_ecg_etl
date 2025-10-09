"""
Complete PDF processing pipeline: anonymization + PNG extraction + PDF merge + compression.

Fluxo:
1. Página 1: Anonimização de texto (remove dados sensíveis)
2. Página 2: Extração como PNG → Aplicação de tarjas → Conversão de volta para PDF
3. Mesclagem: Página 1 + Página 2 = PDF final
4. Compressão: PDF final comprimido (sem perda de qualidade/dimensões)
5. Upload para S3
"""

import io
import fitz  # PyMuPDF
import structlog

from .pdf_anonymizer import anonymize_pdf
from .ecg_extractor import extract_page2_as_png
from .config import DPI_PAGE2_RENDER

logger = structlog.get_logger(__name__)


def process_complete_pdf(pdf_content: bytes, dpi: int = DPI_PAGE2_RENDER) -> bytes:
    """
    Process PDF with complete pipeline: anonymize page 1, extract page 2 as PNG with redactions,
    merge back into single PDF, compress.

    Args:
        pdf_content: Original PDF content as bytes
        dpi: DPI for page 2 PNG extraction (default from config)

    Returns:
        Final compressed PDF as bytes

    Raises:
        ValueError: If PDF has 0 pages
        Exception: If processing fails
    """
    logger.info("Starting complete PDF processing", pdf_size=len(pdf_content), dpi=dpi)

    # Open original PDF
    doc = fitz.open(stream=pdf_content, filetype="pdf")

    try:
        page_count = len(doc)

        if page_count == 0:
            raise ValueError("PDF is empty (0 pages)")

        # === CASO 1: PDF com 1 página ===
        if page_count == 1:
            logger.info("PDF has 1 page, applying anonymization only")
            doc.close()

            # Anonimiza a página 1
            anonymized_pdf = anonymize_pdf(pdf_content)

            logger.info(
                "Single-page PDF processed",
                original_size=len(pdf_content),
                final_size=len(anonymized_pdf),
            )

            return anonymized_pdf

        # === CASO 2: PDF com 2+ páginas ===
        logger.info("PDF has 2+ pages, applying full pipeline")

        # Step 1: Anonimizar página 1 (texto)
        logger.debug("Step 1: Anonymizing page 1")
        anonymized_pdf = anonymize_pdf(pdf_content)

        # Abrir PDF anonimizado
        doc_anon = fitz.open(stream=anonymized_pdf, filetype="pdf")

        # Step 2: Extrair página 2 como PNG com tarjas
        logger.debug("Step 2: Extracting page 2 as PNG with redaction bars")
        png_content = extract_page2_as_png(pdf_content, dpi)

        # Step 3: Converter PNG de volta para PDF
        logger.debug("Step 3: Converting PNG back to PDF")
        page2_pdf = png_to_pdf(png_content, dpi)

        # Step 4: Criar novo PDF mesclando página 1 + página 2
        logger.debug("Step 4: Merging page 1 (anonymized) + page 2 (PNG)")
        final_pdf = merge_pages(doc_anon, page2_pdf)

        # Fechar documentos
        doc_anon.close()
        doc.close()

        logger.info(
            "Multi-page PDF processed successfully",
            original_size=len(pdf_content),
            anonymized_size=len(anonymized_pdf),
            png_size=len(png_content),
            final_size=len(final_pdf),
        )

        return final_pdf

    except Exception as e:
        logger.error(
            "PDF processing failed", error=str(e), error_type=type(e).__name__, exc_info=True
        )
        raise

    finally:
        if not doc.is_closed:
            doc.close()


def png_to_pdf(png_content: bytes, dpi: int = 300) -> bytes:
    """
    Convert PNG image to PDF page maintaining exact dimensions.

    Args:
        png_content: PNG image content as bytes
        dpi: DPI of the PNG image (for size calculation)

    Returns:
        PDF content as bytes with single page
    """
    from PIL import Image

    # Abrir PNG
    img = Image.open(io.BytesIO(png_content))

    # Calcular dimensões em pontos (72 DPI = 1 ponto)
    # Manter dimensões exatas da imagem
    width_pt = img.width * 72 / dpi
    height_pt = img.height * 72 / dpi

    # Criar novo PDF
    pdf_doc = fitz.open()
    page = pdf_doc.new_page(width=width_pt, height=height_pt)

    # Inserir imagem PNG na página (sem redimensionamento)
    # keep_proportion=True mantém proporções exatas
    page.insert_image(
        fitz.Rect(0, 0, width_pt, height_pt), stream=png_content, keep_proportion=True
    )

    # Salvar como bytes
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    logger.debug(
        "PNG converted to PDF",
        png_size=len(png_content),
        pdf_size=len(pdf_bytes),
        width_pt=round(width_pt, 2),
        height_pt=round(height_pt, 2),
    )

    return pdf_bytes


def merge_pages(doc_page1: fitz.Document, page2_pdf_bytes: bytes) -> bytes:
    """
    Merge page 1 from first document + page 2 from second PDF.

    Args:
        doc_page1: Document containing anonymized page 1
        page2_pdf_bytes: PDF bytes containing page 2 (from PNG)

    Returns:
        Merged PDF as bytes
    """
    # Criar novo documento para mesclagem
    merged_doc = fitz.open()

    # Inserir página 1 (anonimizada)
    merged_doc.insert_pdf(doc_page1, from_page=0, to_page=0)

    # Abrir PDF da página 2
    doc_page2 = fitz.open(stream=page2_pdf_bytes, filetype="pdf")

    # Inserir página 2 (PNG convertida)
    merged_doc.insert_pdf(doc_page2, from_page=0, to_page=0)

    # Salvar como bytes
    merged_bytes = merged_doc.tobytes()

    # Fechar documentos
    merged_doc.close()
    doc_page2.close()

    logger.debug("Pages merged successfully", page_count=2, merged_size=len(merged_bytes))

    return merged_bytes


