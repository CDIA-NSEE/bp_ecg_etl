"""BP-ECG ETL Anonymization Pipeline.

A modular, high-performance AWS Lambda function for anonymizing medical PDF documents
containing ECG data. The pipeline processes PDFs from S3, applies intelligent text and
coordinate-based redaction, and outputs anonymized documents to another S3 bucket.

Key Features:
- Intelligent text-based redaction for patient information
- Coordinate-based redaction for fixed layout elements
- Hybrid processing: preserves vector quality for page 1, rasterizes page 2
- Async processing with S3 integration
- Structured logging and comprehensive error handling
- Environment-based configuration with Pydantic validation

"""

# Core modules
from . import config
from . import logging_config

# Processing modules
from . import s3_utils
from . import pdf_anonymizer

# Main entry point
from .main import lambda_handler

__version__ = "2.0.0-simplified"
__author__ = "BP-ECG ETL Team"

__all__ = [
    # Core
    "config",
    "logging_config",
    # Processing
    "s3_utils",
    "pdf_anonymizer", 
    # Main
    "lambda_handler",
]
