"""PDF processing worker for multiprocessing - isolates CPU-bound operations.

This module provides a standalone function that can be executed in separate processes
to parallelize CPU-bound PDF anonymization operations.

NOTE: This is a thin wrapper around pdf_anonymizer.anonymize_pdf() to avoid
code duplication. All anonymization logic lives in pdf_anonymizer.py.
"""

from .pdf_anonymizer import anonymize_pdf


def process_pdf_worker(pdf_content: bytes) -> bytes:
    """Worker function for multiprocessing - anonymize PDF in isolated process.

    This function is designed to be called from ProcessPoolExecutor.
    It performs CPU-intensive PDF processing without blocking the main event loop.

    Args:
        pdf_content: Raw PDF bytes

    Returns:
        Anonymized PDF bytes

    Raises:
        ValueError: If PDF is invalid
        Exception: If anonymization fails
    """
    # Simply delegate to the main anonymization function
    # The function is already designed to be process-safe and thread-safe
    return anonymize_pdf(pdf_content)
