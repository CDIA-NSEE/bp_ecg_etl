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
from .config import *
from . import constants
from .constants import *
from . import logging_config
from .logging_config import setup_logging
from . import models
from .models import *
from . import validators
from .validators import *
from . import s3_utils
from .s3_utils import *
from . import pdf_anonymizer
from .pdf_anonymizer import anonymize_pdf

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
    # Main
    "main",
]
