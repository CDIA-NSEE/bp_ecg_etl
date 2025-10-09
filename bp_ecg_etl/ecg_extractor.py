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

        # STEP 1: Rasterize page FIRST (this automatically handles rotation)
        # PyMuPDF applies rotation during rendering, so output is in visual orientation
        zoom = dpi / 72.0  # 72 DPI is PDF standard
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        # Convert PyMuPDF pixmap to PIL Image
        img = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

        logger.debug(
            "ECG page rendered to image",
            page_label=page_label,
            width=img.width,
            height=img.height,
            mode=img.mode,
        )

        # STEP 2: Apply black bars on rasterized image
        # Coordinates are in visual orientation (origin: top-left)
        # This permanently destroys sensitive data
        if redact_coords:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)

            for idx, coords in enumerate(redact_coords):
                x0_val, y0_val, x1_val, y1_val = coords

                # Auto-detect if coordinates are relative (0-1) or absolute (>1)
                if all(0 <= c <= 1 for c in coords):
                    # Relative coordinates - convert to absolute pixels
                    x0 = int(x0_val * img.width)
                    y0 = int(y0_val * img.height)
                    x1 = int(x1_val * img.width)
                    y1 = int(y1_val * img.height)
                else:
                    # Absolute coordinates - use directly
                    x0, y0, x1, y1 = int(x0_val), int(y0_val), int(x1_val), int(y1_val)

                # Draw black rectangle on image
                draw.rectangle([x0, y0, x1, y1], fill=(0, 0, 0))

                logger.debug(
                    "Applied redaction bar",
                    page_label=page_label,
                    bar_index=idx,
                    coords=(x0, y0, x1, y1),
                )

        logger.debug(
            "ECG page rasterized with redactions",
            page_label=page_label,
            width=img.width,
            height=img.height,
            mode=img.mode,
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
