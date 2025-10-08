"""Tests for configuration."""

from bp_ecg_etl.config import (
    INPUT_BUCKET,
    OUTPUT_BUCKET,
    AWS_REGION,
    MAX_WORKERS,
    QUEUE_SIZE,
    DPI_PAGE2_RENDER,
)


class TestConfigDefaults:
    """Test configuration default values."""
    
    def test_input_bucket_default(self):
        """Test INPUT_BUCKET default value."""
        assert INPUT_BUCKET == "raw-pdfs"
    
    def test_output_bucket_default(self):
        """Test OUTPUT_BUCKET default value."""
        assert OUTPUT_BUCKET == "anon-pdfs"
    
    def test_aws_region_default(self):
        """Test AWS_REGION default value."""
        assert AWS_REGION == "us-east-1"
    
    def test_max_workers_default(self):
        """Test MAX_WORKERS default for ECS."""
        assert MAX_WORKERS == 50
    
    def test_queue_size_default(self):
        """Test QUEUE_SIZE default."""
        assert QUEUE_SIZE == 200
    
    def test_dpi_default(self):
        """Test DPI_PAGE2_RENDER default."""
        assert DPI_PAGE2_RENDER == 150


class TestConfigTypes:
    """Test configuration types."""
    
    def test_max_workers_is_int(self):
        """Test MAX_WORKERS is integer."""
        assert isinstance(MAX_WORKERS, int)
        assert MAX_WORKERS > 0
    
    def test_queue_size_is_int(self):
        """Test QUEUE_SIZE is integer."""
        assert isinstance(QUEUE_SIZE, int)
        assert QUEUE_SIZE > 0
    
    def test_dpi_is_int(self):
        """Test DPI_PAGE2_RENDER is integer."""
        assert isinstance(DPI_PAGE2_RENDER, int)
        assert DPI_PAGE2_RENDER > 0
