"""Input validators for BP-ECG ETL."""


def validate_pdf_content(content: bytes) -> None:
    """Validate PDF content before processing.
    
    Args:
        content: Raw PDF bytes
        
    Raises:
        ValueError: If content is invalid
    """
    if not content or len(content) < 100:
        raise ValueError(f"Invalid PDF: content too small ({len(content)} bytes)")
    
    if not content.startswith(b'%PDF'):
        raise ValueError("Invalid PDF: missing PDF header")


def validate_s3_key(key: str) -> None:
    """Validate S3 key format.
    
    Args:
        key: S3 object key
        
    Raises:
        ValueError: If key format is invalid
    """
    if not key:
        raise ValueError("S3 key cannot be empty")
    
    if not key.endswith('.pdf'):
        raise ValueError(f"Invalid S3 key: must end with .pdf (got: {key})")
    
    # Check for invalid characters
    if any(char in key for char in ['\\', '\0']):
        raise ValueError(f"Invalid S3 key: contains invalid characters ({key})")


def validate_bucket_name(bucket: str) -> None:
    """Validate S3 bucket name format.
    
    Args:
        bucket: S3 bucket name
        
    Raises:
        ValueError: If bucket name is invalid
    """
    if not bucket:
        raise ValueError("Bucket name cannot be empty")
    
    if len(bucket) < 3 or len(bucket) > 63:
        raise ValueError(f"Invalid bucket name: must be 3-63 characters (got: {len(bucket)})")
    
    # Basic S3 bucket naming rules
    if not bucket[0].isalnum() or not bucket[-1].isalnum():
        raise ValueError("Bucket name must start and end with letter or number")


def validate_page_count(page_count: int) -> None:
    """Validate PDF page count.
    
    Args:
        page_count: Number of pages in PDF
        
    Raises:
        ValueError: If page count is invalid
    """
    if page_count < 1:
        raise ValueError(f"Invalid page count: must be >= 1 (got: {page_count})")
    
    if page_count > 10:
        raise ValueError(f"Invalid page count: too many pages (got: {page_count})")
