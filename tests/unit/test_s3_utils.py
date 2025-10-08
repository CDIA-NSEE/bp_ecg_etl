"""Tests for S3 utilities."""

from datetime import datetime

from bp_ecg_etl.s3_utils import generate_output_key_with_date


class TestOutputKeyGeneration:
    """Test output key generation with date partitioning."""
    
    def test_generate_output_key_with_date(self):
        """Test Hive-style date partitioning."""
        input_key = "folder/subfolder/file.pdf"
        output_key = generate_output_key_with_date(input_key)
        
        # Should contain year/month/day partitions
        assert "year=" in output_key
        assert "month=" in output_key
        assert "day=" in output_key
        
        # Should end with .pdf.gz
        assert output_key.endswith(".pdf.gz")
        
        # Should contain ULID
        assert "anonymized_" in output_key
    
    def test_output_key_current_date(self):
        """Test that output key uses current date."""
        now = datetime.utcnow()
        output_key = generate_output_key_with_date("test.pdf")
        
        # Verify year/month/day match current date
        assert f"year={now.year}" in output_key
        assert f"month={now.month:02d}" in output_key
        assert f"day={now.day:02d}" in output_key
    
    def test_output_key_preserves_directory_structure(self):
        """Test that directory structure is preserved."""
        input_key = "deep/nested/folder/file.pdf"
        output_key = generate_output_key_with_date(input_key)
        
        # Should preserve the directory prefix
        assert output_key.startswith("deep/nested/folder/")
