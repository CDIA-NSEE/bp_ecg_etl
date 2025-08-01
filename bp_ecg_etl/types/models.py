"""Type definitions for BP-ECG ETL."""

from typing import Dict, Optional, Any, Protocol, runtime_checkable
from dataclasses import dataclass
from enum import Enum


class ProcessingStatus(str, Enum):
    """Status of PDF processing operations."""
    SUCCESS = "success"
    ERROR = "error"
    DONE = "done"


@dataclass
class ProcessingResult:
    """Result of processing a single PDF."""
    file_id: str
    status: ProcessingStatus
    text: Optional[str] = None
    images: Optional[str] = None  # Comma-separated S3 URIs
    error: Optional[str] = None
    processing_time_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataFrame creation."""
        return {
            "file_id": self.file_id,
            "status": self.status.value,
            "text": self.text,
            "images": self.images,
            "error": self.error,
            "processing_time_ms": self.processing_time_ms,
        }


@dataclass
class BatchResult:
    """Result of processing a batch of PDFs."""
    batch_id: int
    processed: int
    success: int
    errors: int
    processing_time_ms: int
    status: ProcessingStatus = ProcessingStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "batch_id": self.batch_id,
            "processed": self.processed,
            "success": self.success,
            "errors": self.errors,
            "processing_time_ms": self.processing_time_ms,
            "status": self.status.value,
        }


@runtime_checkable
class S3Client(Protocol):
    """Type protocol for S3 client."""
    def get_object(self, **kwargs) -> Any: ...
    def put_object(self, **kwargs) -> Any: ...
    def get_paginator(self, operation_name: str) -> Any: ...


@runtime_checkable
class LambdaClient(Protocol):
    """Type protocol for Lambda client."""
    def invoke(self, **kwargs) -> Any: ...


# Type aliases
CropRegion = Any  # fitz.Rect
PDFDocument = Any  # fitz.Document
Logger = Any  # structlog logger
