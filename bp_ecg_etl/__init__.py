"""BP-ECG ETL Anonymization Pipeline.

A modular, high-performance ECS Fargate service for anonymizing medical PDF documents
containing ECG data. The pipeline processes PDFs from S3, applies intelligent text and
coordinate-based redaction, and outputs anonymized documents to another S3 bucket.

Key Features:
- Intelligent text-based redaction for patient information
- Coordinate-based redaction for fixed layout elements
- VECTORIAL redaction: preserves vector quality for all pages
- ZIP compression for storage optimization
- Date-based partitioning (/YYYY/mm) for output files
- Async batch processing with S3 streaming
- Structured logging and comprehensive error handling
- Environment-based configuration

"""

# Core modules
from . import config, logging_config, pdf_anonymizer, s3_utils
from .config import *
from .logging_config import setup_logging

# Main entry point
from .main import main
from .pdf_anonymizer import anonymize_pdf
from .s3_utils import *

__version__ = "3.1.0-vectorial"

__all__ = [
    "config",
    "logging_config",
    "main",
    "pdf_anonymizer",
    "s3_utils",
    "anonymize_pdf",
    "setup_logging",
]
