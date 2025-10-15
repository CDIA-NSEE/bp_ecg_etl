"""PDF anonymization with intelligent text and coordinate-based redaction."""

import io

import fitz  # PyMuPDF
import structlog

from .config import (
    CRM_TOKENS,
    KEEP_LABELS,
    LABELS_SAME_LINE,
    LINE_TOLERANCE,
    PADDING,
    PAGE1_REDACT_COORDS,
    PAGE2_REDACT_COORDS,
    PREVLINE_TOLERANCE,
)

logger = structlog.get_logger(__name__)

# Type aliases for clarity
Word = tuple[float, float, float, float, str]  # x0, y0, x1, y1, text
Line = list[Word]
Coordinates = tuple[float, float, float, float]


def clamp01(v: float) -> float:
    """Clamp coordinate value to 0-1 range."""
    return max(0.0, min(1.0, float(v)))


def to_abs_rect(page: fitz.Page, rel_rect: tuple[float, float, float, float]) -> fitz.Rect:
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


def clear_pdf_metadata(doc: fitz.Document) -> None:
    """Clear all metadata from PDF document for privacy.

    Removes standard metadata, XMP metadata, and document info.

    Args:
        doc: PyMuPDF document object
    """
    logger.debug("Clearing PDF metadata")

    # Clear standard metadata fields
    try:
        doc.set_metadata({})
    except Exception as e:
        logger.warning("Could not clear standard metadata", error=str(e))

    # Clear XMP metadata
    try:
        if doc.get_xml_metadata():
            doc.set_xml_metadata("")
    except Exception as e:
        logger.warning("Could not clear XMP metadata", error=str(e))

    logger.debug("PDF metadata cleared")


def words_by_line(page: fitz.Page) -> list[Line]:
    """Extract and group words by text lines with vertical proximity.

    Args:
        page: PyMuPDF page object

    Returns:
        List of lines, where each line is a list of word tuples
    """
    words = page.get_text("words")  # Returns list of (x0, y0, x1, y1, text, ...)
    if not words:
        return []

    # Filter empty words and sort by vertical position, then horizontal
    valid_words: list[Word] = [(w[0], w[1], w[2], w[3], w[4]) for w in words if w[4].strip()]
    valid_words.sort(key=lambda w: (round(w[1], 1), w[0]))

    # Group words into lines based on vertical proximity
    lines: list[Line] = []
    current_line: Line = []
    prev_y: float | None = None

    for word in valid_words:
        y0 = word[1]
        if prev_y is None or abs(y0 - prev_y) <= LINE_TOLERANCE:
            current_line.append(word)
            prev_y = y0 if prev_y is None else (prev_y + y0) / 2.0
        else:
            if current_line:
                lines.append(current_line)
            current_line = [word]
            prev_y = y0

    if current_line:
        lines.append(current_line)

    return lines


def rect_of_words(words_line: list[Word], start_idx: int, end_idx: int) -> fitz.Rect:
    """Create bounding rectangle from word range with padding.

    Args:
        words_line: Line containing words
        start_idx: Start index (inclusive)
        end_idx: End index (exclusive)

    Returns:
        Rectangle encompassing the words with padding
    """
    words = words_line[start_idx:end_idx]
    if not words:
        return fitz.Rect(0, 0, 0, 0)

    xs0 = [w[0] for w in words]
    ys0 = [w[1] for w in words]
    xs1 = [w[2] for w in words]
    ys1 = [w[3] for w in words]

    return fitz.Rect(
        min(xs0) - PADDING,
        min(ys0) - PADDING,
        max(xs1) + PADDING,
        max(ys1) + PADDING,
    )


def redact_line_values_after_label(
    page: fitz.Page, lines: list[list[Word]], labels_set: set[str]
) -> None:
    """Redact values after specific labels on the same line.

    Args:
        page: PyMuPDF page object
        lines: Pre-computed lines from words_by_line()
        labels_set: Set of labels to search for
    """
    for line in lines:
        texts = [w[4] for w in line]

        for i, token in enumerate(texts):
            # Normalize token (add colon if missing)
            normalized = token if token.endswith(":") else f"{token}:"

            # Skip if not a label to redact or if in keep list
            if normalized not in labels_set or normalized in KEEP_LABELS:
                continue

            start_idx = i + 1
            if start_idx >= len(line):
                continue

            # Find end index (next label or end of line)
            end_idx = len(line)
            for j in range(start_idx, len(texts)):
                next_normalized = texts[j] if texts[j].endswith(":") else f"{texts[j]}:"
                if next_normalized in labels_set or next_normalized in KEEP_LABELS:
                    end_idx = j
                    break

            # Add redaction annotation
            if end_idx > start_idx:
                rect = rect_of_words(line, start_idx, end_idx)
                page.add_redact_annot(rect, fill=(0, 0, 0))


def redact_crm_and_upper_name(page: fitz.Page, lines: list[list[Word]]) -> None:
    """Redact CRM tokens and signature lines above them.

    Args:
        page: PyMuPDF page object
        lines: Pre-computed lines from words_by_line()
    """
    # Redact CRM tokens and everything to their right
    for line in lines:
        texts = [w[4] for w in line]
        for i, token in enumerate(texts):
            if token.strip() in CRM_TOKENS:
                rect = rect_of_words(line, i, len(line))
                page.add_redact_annot(rect, fill=(0, 0, 0))

    # Find all CRM positions
    crm_rects: list[fitz.Rect] = []
    for crm_token in CRM_TOKENS:
        crm_rects.extend(page.search_for(crm_token, quads=False))

    if not crm_rects:
        return

    # Build line rectangles for searching
    line_rects = [(rect_of_words(line, 0, len(line)), line) for line in lines]

    # Redact signature line above each CRM (if not a label)
    for crm_rect in crm_rects:
        # Find lines above CRM within tolerance
        candidates: list[tuple[float, fitz.Rect, Line]] = []
        for rect, line in line_rects:
            # Check if line is above CRM and within vertical/horizontal tolerance
            if (
                rect.y1 <= crm_rect.y0
                and (crm_rect.y0 - rect.y1) <= PREVLINE_TOLERANCE
                and rect.x1 > crm_rect.x0 - 50
                and rect.x0 < crm_rect.x1 + 50
            ):
                distance = crm_rect.y0 - rect.y1
                candidates.append((distance, rect, line))

        if candidates:
            # Get closest line above CRM
            candidates.sort(key=lambda t: t[0])
            _, rect, line = candidates[0]

            # Only redact if not a label line (no colon)
            line_text = " ".join(w[4] for w in line)
            if ":" not in line_text:
                page.add_redact_annot(rect, fill=(0, 0, 0))


def anonymize_text_on_page1(page1: fitz.Page, lines: list[list[Word]]) -> None:
    """Apply text-based anonymization to page 1.

    Args:
        page1: PyMuPDF page object
        lines: Pre-computed lines from words_by_line()
    """
    # Include ALL labels for proper next-label detection
    # The redaction logic filters out KEEP_LABELS automatically
    labels_set = set(LABELS_SAME_LINE + KEEP_LABELS)
    redact_line_values_after_label(page1, lines, labels_set)
    redact_crm_and_upper_name(page1, lines)


def anonymize_single_page_pdf(doc: fitz.Document) -> bytes:
    """Anonymize PDF with only 1 page using VECTORIAL redaction.

    Args:
        doc: PyMuPDF document object

    Returns:
        Anonymized PDF as bytes
    """
    logger.info("Processing single-page PDF (vectorial)")

    page1 = doc[0]

    # Extract lines once for performance
    lines = words_by_line(page1)
    labels_set = set(LABELS_SAME_LINE + KEEP_LABELS)

    # Apply text-based redactions
    redact_line_values_after_label(page1, lines, labels_set)
    redact_crm_and_upper_name(page1, lines)

    # Apply coordinate-based redaction for page 1
    for coords in PAGE1_REDACT_COORDS:
        page1.add_redact_annot(to_abs_rect(page1, coords), fill=(0, 0, 0))

    # For single-page PDFs, also apply PAGE2 coordinates (ECG is on page 1)
    for coords in PAGE2_REDACT_COORDS:
        page1.add_redact_annot(to_abs_rect(page1, coords), fill=(0, 0, 0))

    # Apply all redactions vectorially (preserves vector format)
    page1.apply_redactions()

    # Clear PDF metadata for privacy
    clear_pdf_metadata(doc)

    # Save with maximum security flags
    output_buffer = io.BytesIO()
    doc.save(
        output_buffer,
        garbage=4,      # Maximum garbage collection
        clean=True,     # Clean internal structure
        deflate=True,   # Compress streams
        pretty=False,   # No formatting
        linear=False,   # No linearization
    )

    logger.info("Single-page PDF vectorial anonymization completed")
    return output_buffer.getvalue()


def anonymize_multi_page_pdf(doc: fitz.Document) -> bytes:
    """Anonymize PDF with 2+ pages using VECTORIAL redaction.

    Args:
        doc: PyMuPDF document object

    Returns:
        Anonymized PDF as bytes
    """
    logger.info("Processing multi-page PDF (vectorial)", pages=len(doc))

    # Process Page 1: Text + Coordinate redaction (vectorial)
    page1 = doc[0]
    lines_page1 = words_by_line(page1)

    # Apply text-based redaction
    anonymize_text_on_page1(page1, lines_page1)

    # Apply coordinate-based redaction for page 1
    for coords in PAGE1_REDACT_COORDS:
        page1.add_redact_annot(to_abs_rect(page1, coords), fill=(0, 0, 0))
    page1.apply_redactions()

    # Process Page 2: Vectorial redaction (no rasterization)
    page2 = doc[1]

    # Apply coordinate-based redaction for page 2
    for coords in PAGE2_REDACT_COORDS:
        page2.add_redact_annot(to_abs_rect(page2, coords), fill=(0, 0, 0))

    # Apply vectorial redactions on page 2
    page2.apply_redactions()

    # Clear PDF metadata for privacy
    clear_pdf_metadata(doc)

    # Save final PDF with maximum security flags
    output_buffer = io.BytesIO()
    doc.save(
        output_buffer,
        garbage=4,      # Maximum garbage collection
        clean=True,     # Clean internal structure
        deflate=True,   # Compress streams
        pretty=False,   # No formatting
        linear=False,   # No linearization
    )

    logger.info("Multi-page PDF vectorial anonymization completed")
    return output_buffer.getvalue()


def anonymize_pdf(pdf_content: bytes) -> bytes:
    """Main anonymization function with conditional logic based on page count.

    Args:
        pdf_content: Raw PDF bytes

    Returns:
        Anonymized PDF bytes

    Raises:
        ValueError: If PDF is invalid or has 0 pages
        Exception: If anonymization fails
    """
    # Validate input
    if not pdf_content or len(pdf_content) < 100:
        logger.error("Invalid PDF: content too small", size=len(pdf_content))
        raise ValueError(f"Invalid PDF: content too small ({len(pdf_content)} bytes)")

    if not pdf_content.startswith(b"%PDF"):
        logger.error("Invalid PDF: missing PDF header")
        raise ValueError("Invalid PDF: missing PDF header")

    logger.info("Starting PDF anonymization", pdf_size=len(pdf_content))

    # Open PDF
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
    except Exception as e:
        logger.error("Failed to open PDF", error=str(e), error_type=type(e).__name__)
        raise ValueError(f"Failed to open PDF: {e}") from e

    page_count = len(doc)
    logger.info("PDF page count detected", pages=page_count)

    if page_count == 0:
        doc.close()
        logger.error("Invalid PDF: no pages found")
        raise ValueError("PDF must have at least 1 page")

    try:
        if page_count == 1:
            result = anonymize_single_page_pdf(doc)
        elif page_count >= 2:
            result = anonymize_multi_page_pdf(doc)
        else:
            raise ValueError("Invalid page count")

        logger.info(
            "PDF anonymization completed",
            pages=page_count,
            original_size=len(pdf_content),
            output_size=len(result),
        )

        return result

    except Exception as e:
        logger.error(
            "PDF anonymization failed",
            error=str(e),
            error_type=type(e).__name__,
            pages=page_count,
            exc_info=True,
        )
        raise

    finally:
        doc.close()
