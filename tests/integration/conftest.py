"""Integration test fixtures."""

import pytest


@pytest.fixture
def mock_s3_bucket():
    """Mock S3 bucket for integration tests."""
    # Placeholder for moto or localstack integration
    return "test-bucket"


@pytest.fixture
def integration_pdf_path(test_data_dir):
    """Path to integration test PDF."""
    return test_data_dir / "exemplo1.pdf"
