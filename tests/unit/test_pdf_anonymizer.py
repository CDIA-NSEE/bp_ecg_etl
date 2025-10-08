"""Tests for PDF anonymization."""

import fitz
import pytest

from bp_ecg_etl.pdf_anonymizer import (
    anonymize_pdf,
    words_by_line,
    clamp01,
)


class TestValidation:
    """Test input validation."""
    
    def test_empty_pdf_raises_error(self, empty_pdf: bytes):
        """Test that empty PDF raises ValueError."""
        with pytest.raises(ValueError, match="content too small"):
            anonymize_pdf(empty_pdf)
    
    def test_invalid_pdf_raises_error(self, invalid_pdf: bytes):
        """Test that invalid PDF raises ValueError."""
        with pytest.raises(ValueError, match="content too small"):
            anonymize_pdf(invalid_pdf)
    
    def test_too_small_pdf_raises_error(self):
        """Test that PDF < 100 bytes raises ValueError."""
        with pytest.raises(ValueError, match="content too small"):
            anonymize_pdf(b"%PDF-1.4\n")


class TestSinglePageAnonymization:
    """Test single-page PDF anonymization."""
    
    def test_single_page_anonymization(self, sample_pdf_1page: bytes):
        """Test that single-page PDF is anonymized successfully."""
        result = anonymize_pdf(sample_pdf_1page)
        
        # Verify it's a valid PDF
        assert result.startswith(b'%PDF')
        
        # Verify it has 1 page
        doc = fitz.open(stream=result, filetype="pdf")
        assert len(doc) == 1
        doc.close()
    
    def test_single_page_preserves_structure(self, sample_pdf_1page: bytes):
        """Test that single-page PDF maintains structure."""
        result = anonymize_pdf(sample_pdf_1page)
        
        # Open and verify
        doc = fitz.open(stream=result, filetype="pdf")
        assert len(doc) == 1
        
        # Verify page dimensions are reasonable
        page = doc[0]
        assert page.rect.width > 0
        assert page.rect.height > 0
        doc.close()


class TestMultiPageAnonymization:
    """Test multi-page PDF anonymization."""
    
    def test_multi_page_anonymization(self, sample_pdf_2page: bytes):
        """Test that multi-page PDF is anonymized successfully."""
        result = anonymize_pdf(sample_pdf_2page)
        
        # Verify it's a valid PDF
        assert result.startswith(b'%PDF')
        
        # Verify it has 2 pages
        doc = fitz.open(stream=result, filetype="pdf")
        assert len(doc) == 2
        doc.close()
    
    def test_multi_page_preserves_dimensions(self, sample_pdf_2page: bytes):
        """Test that page 2 maintains original dimensions."""
        # Get original dimensions
        original_doc = fitz.open(stream=sample_pdf_2page, filetype="pdf")
        original_page2_rect = original_doc[1].rect
        original_width = original_page2_rect.width
        original_height = original_page2_rect.height
        original_doc.close()
        
        # Anonymize
        result = anonymize_pdf(sample_pdf_2page)
        
        # Check anonymized dimensions
        result_doc = fitz.open(stream=result, filetype="pdf")
        result_page2_rect = result_doc[1].rect
        result_width = result_page2_rect.width
        result_height = result_page2_rect.height
        result_doc.close()
        
        # Verify dimensions match (within 1 point tolerance for rounding)
        assert abs(result_width - original_width) < 1.0
        assert abs(result_height - original_height) < 1.0


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_clamp01(self):
        """Test coordinate clamping."""
        assert clamp01(0.5) == 0.5
        assert clamp01(-0.1) == 0.0
        assert clamp01(1.5) == 1.0
        assert clamp01(0.0) == 0.0
        assert clamp01(1.0) == 1.0
    
    def test_words_by_line(self, sample_pdf_1page: bytes):
        """Test word extraction and line grouping."""
        doc = fitz.open(stream=sample_pdf_1page, filetype="pdf")
        page = doc[0]
        
        lines = words_by_line(page)
        
        # Should have at least some lines
        assert len(lines) > 0
        
        # Each line should be a list of word tuples
        for line in lines:
            assert isinstance(line, list)
            for word in line:
                assert len(word) == 5  # (x0, y0, x1, y1, text)
        
        doc.close()


class TestMetadataRemoval:
    """Test metadata removal."""
    
    def test_metadata_is_cleared(self, sample_pdf_1page: bytes):
        """Test that sensitive PDF metadata is removed."""
        result = anonymize_pdf(sample_pdf_1page)
        
        doc = fitz.open(stream=result, filetype="pdf")
        metadata = doc.metadata
        
        # Sensitive metadata fields should be empty
        sensitive_fields = ['title', 'author', 'subject', 'keywords', 'creator', 'producer']
        for field in sensitive_fields:
            assert not metadata.get(field) or metadata.get(field) == "", f"{field} should be empty"
        
        doc.close()
