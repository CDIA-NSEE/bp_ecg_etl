"""Domain models for BP-ECG ETL."""

from dataclasses import dataclass


@dataclass
class ProcessingResult:
    """Result of a single PDF processing operation."""

    input_key: str
    output_key: str
    original_size: int
    output_size: int
    pages: int
    success: bool
    error: str | None = None
    duration_sec: float = 0.0

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio."""
        if self.original_size == 0:
            return 0.0
        return (self.output_size / self.original_size) * 100

    @property
    def size_reduction_pct(self) -> float:
        """Calculate size reduction percentage."""
        if self.original_size == 0:
            return 0.0
        return ((self.original_size - self.output_size) / self.original_size) * 100


@dataclass
class ProcessingStats:
    """Aggregated statistics for batch processing."""

    total: int = 0
    successful: int = 0
    failed: int = 0
    total_time_sec: float = 0.0
    total_original_bytes: int = 0
    total_output_bytes: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.successful / self.total) * 100

    @property
    def avg_compression_ratio(self) -> float:
        """Calculate average compression ratio."""
        if self.total_original_bytes == 0:
            return 0.0
        return (self.total_output_bytes / self.total_original_bytes) * 100

    @property
    def avg_duration_sec(self) -> float:
        """Calculate average processing duration per PDF."""
        if self.total == 0:
            return 0.0
        return self.total_time_sec / self.total


@dataclass
class PDFMetadata:
    """Metadata about a PDF file."""

    s3_key: str
    size_bytes: int
    page_count: int = 0
    created_at: str | None = None

    @property
    def size_mb(self) -> float:
        """Size in megabytes."""
        return self.size_bytes / (1024 * 1024)
