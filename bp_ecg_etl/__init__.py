"""BP-ECG ETL Anonymization Pipeline.

A modular, high-performance ECS Fargate service for anonymizing medical PDF documents
containing ECG data. The pipeline processes PDFs from S3, applies intelligent text and
coordinate-based redaction, and outputs anonymized documents to another S3 bucket.

Key Features:
- Intelligent text-based redaction for patient information
- Coordinate-based redaction for fixed layout elements
- Hybrid processing: preserves vector quality for page 1, rasterizes page 2
- Async batch processing with S3 streaming
- Structured logging and comprehensive error handling
- Environment-based configuration
- CloudWatch metrics integration

"""

# Core modules
from . import config
from . import constants
from . import logging_config
from . import models
from . import validators

# Processing modules
from . import s3_utils
from . import pdf_anonymizer
from . import metrics

# Main entry point
from .main import main

__version__ = "3.0.0-ecs"
__author__ = "BP-ECG ETL Team"

__all__ = [
    # Core
    "config",
    "constants",
    "logging_config",
    "models",
    "validators",
    # Processing
    "s3_utils",
    "pdf_anonymizer",
    "metrics",
    # Main
    "main",
]
