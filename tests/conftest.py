"""Pytest configuration and fixtures."""

import io
from pathlib import Path

import pytest
import fitz


@pytest.fixture
def test_data_dir() -> Path:
    """Return path to test data directory."""
    return Path(__file__).parent.parent / "test_data"


@pytest.fixture
def sample_pdf_1page(test_data_dir: Path) -> bytes:
    """Load sample 1-page PDF."""
    pdf_path = test_data_dir / "exemplo3.pdf"
    if not pdf_path.exists():
        # Create a minimal 1-page PDF for testing
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)  # A4 size
        page.insert_text((100, 100), "Nome: Test Patient", fontsize=12)
        page.insert_text((100, 120), "CPF: 123.456.789-00", fontsize=12)
        page.insert_text((100, 140), "Sexo: M", fontsize=12)
        
        buffer = io.BytesIO()
        doc.save(buffer)
        doc.close()
        return buffer.getvalue()
    
    with open(pdf_path, "rb") as f:
        return f.read()


@pytest.fixture
def sample_pdf_2page(test_data_dir: Path) -> bytes:
    """Load sample 2-page PDF."""
    pdf_path = test_data_dir / "exemplo1.pdf"
    if not pdf_path.exists():
        # Create a minimal 2-page PDF for testing
        doc = fitz.open()
        
        # Page 1
        page1 = doc.new_page(width=595, height=842)
        page1.insert_text((100, 100), "Nome: Test Patient", fontsize=12)
        page1.insert_text((100, 120), "CPF: 123.456.789-00", fontsize=12)
        
        # Page 2
        page2 = doc.new_page(width=595, height=842)
        page2.insert_text((100, 100), "ECG Data", fontsize=12)
        
        buffer = io.BytesIO()
        doc.save(buffer)
        doc.close()
        return buffer.getvalue()
    
    with open(pdf_path, "rb") as f:
        return f.read()


@pytest.fixture
def invalid_pdf() -> bytes:
    """Return invalid PDF content."""
    return b"This is not a PDF"


@pytest.fixture
def empty_pdf() -> bytes:
    """Return empty content."""
    return b""
