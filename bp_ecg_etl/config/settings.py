"""Configuration settings for BP-ECG ETL."""

import os
from typing import List, Optional
import fitz
from ..types import CropRegion


class Settings:
    """Application settings loaded from environment variables."""
    
    def __init__(self):
        self.SOURCE_BUCKET: str = os.environ.get("SOURCE_BUCKET", "your-source-bucket")
        self.DEST_BUCKET: str = os.environ.get("DEST_BUCKET", "your-dest-bucket")
        self.PDF_PREFIX: str = os.environ.get("PDF_PREFIX", "pdfs/")
        self.BATCH_SIZE: int = int(os.environ.get("BATCH_SIZE", "100"))
        self.CONCURRENCY: int = int(os.environ.get("CONCURRENCY", "20"))
        self.LAMBDA_NAME: Optional[str] = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        self.CROP_REGIONS: List[CropRegion] = [fitz.Rect(100, 100, 300, 300)]


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings (singleton pattern)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
