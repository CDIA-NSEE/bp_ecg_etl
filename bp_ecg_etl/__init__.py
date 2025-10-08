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
from . import config, constants, logging_config, models, pdf_anonymizer, s3_utils, validators
from .config import *
from .constants import *
from .logging_config import setup_logging

# Main entry point
from .main import main
from .models import *
from .pdf_anonymizer import anonymize_pdf
from .s3_utils import *
from .validators import *

__version__ = "3.0.0-ecs"

__all__ = [
    "config",
    "constants",
    "logging_config",
    "main",
    "models",
    "pdf_anonymizer",
    "s3_utils",
    "validators",
]
