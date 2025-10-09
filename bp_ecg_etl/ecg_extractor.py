"""
High-performance ECG image extraction from PDF page 2.
Extracts page 2 as PNG with full quality and applies vectorial black bars.
"""

import io
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import structlog

from .config import PAGE1_REDACT_COORDS, PAGE2_REDACT_COORDS

logger = structlog.get_logger(__name__)


def clamp01(v: float) -> float:
    """Clamp coordinate value to 0-1 range."""
    return max(0.0, min(1.0, float(v)))


def extract_page2_as_png(pdf_content: bytes, dpi: int = 300) -> bytes:
    """
    Extract ECG page from PDF as high-quality PNG with black bar redactions.

    Logic:
    - If PDF has 2+ pages: Extract page 2 with PAGE2_REDACT_COORDS
    - If PDF has 1 page: Extract page 1 with PAGE1_REDACT_COORDS

    Args:
        pdf_content: PDF file content as bytes
        dpi: Resolution for image extraction (default 300 DPI for high quality)

    Returns:
        PNG image content as bytes

    Raises:
        ValueError: If PDF has 0 pages
        Exception: If extraction or processing fails
    """
    logger.debug("Starting ECG page extraction", pdf_size=len(pdf_content), dpi=dpi)

    # Open PDF from bytes
    doc = fitz.open(stream=pdf_content, filetype="pdf")

    try:
        page_count = len(doc)

        if page_count == 0:
            raise ValueError("PDF is empty (0 pages)")

        # Determine which page and redaction coords to use
        if page_count >= 2:
            page_index = 1  # Page 2
            redact_coords = PAGE2_REDACT_COORDS
            page_label = "page_2"
            logger.debug("PDF has 2+ pages, extracting page 2")
        else:
            page_index = 0  # Page 1
            redact_coords = PAGE1_REDACT_COORDS
            page_label = "page_1"
            logger.debug("PDF has 1 page, extracting page 1")

        # Get the target page
        page = doc[page_index]

        # Render page to pixmap with specified DPI
        zoom = dpi / 72.0  # 72 DPI is PDF standard
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        # Convert PyMuPDF pixmap to PIL Image
        img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

        logger.debug(
            "ECG page rendered to image",
            page_label=page_label,
            width=img.width,
            height=img.height,
            mode=img.mode,
        )

        # Apply black bars for sensitive data redaction
        if redact_coords:
            draw = ImageDraw.Draw(img)

            for idx, coords in enumerate(redact_coords):
                # Normalize coordinates to 0-1 range
                x0, y0, x1, y1 = coords

                # Check if coordinates are already normalized (0-1 range)
                if all(0 <= c <= 1 for c in coords):
                    # Convert relative coordinates to absolute pixels
                    x0_px = int(x0 * img.width)
                    y0_px = int(y0 * img.height)
                    x1_px = int(x1 * img.width)
                    y1_px = int(y1 * img.height)
                else:
                    # Use absolute pixel coordinates directly
                    x0_px, y0_px, x1_px, y1_px = int(x0), int(y0), int(x1), int(y1)

                # Ensure proper rectangle (x0 < x1, y0 < y1)
                if x0_px > x1_px:
                    x0_px, x1_px = x1_px, x0_px
                if y0_px > y1_px:
                    y0_px, y1_px = y1_px, y0_px

                # Draw black rectangle (vectorial bar)
                draw.rectangle([x0_px, y0_px, x1_px, y1_px], fill=(0, 0, 0))

                logger.debug(
                    "Applied redaction bar",
                    page_label=page_label,
                    bar_index=idx,
                    coords=(x0_px, y0_px, x1_px, y1_px),
                )

        # Save as PNG with maximum quality (lossless)
        output = io.BytesIO()
        img.save(output, format="PNG", optimize=False, compress_level=0)
        png_content = output.getvalue()

        logger.info(
            "ECG page successfully extracted as PNG",
            page_label=page_label,
            page_count=page_count,
            input_size=len(pdf_content),
            output_size=len(png_content),
            width=img.width,
            height=img.height,
            dpi=dpi,
            redaction_bars_applied=len(redact_coords) if redact_coords else 0,
        )

        return png_content

    finally:
        doc.close()
