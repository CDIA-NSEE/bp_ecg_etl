"""BP-ECG ETL package for processing PDF documents from S3."""

__version__ = "1.0.0"

from .main import lambda_handler

__all__ = ["lambda_handler"]
