"""S3 utilities for PDF processing with connection pooling."""

import aioboto3
import structlog
from botocore.exceptions import ClientError
import ulid as ulid_lib

from .config import AWS_REGION

logger = structlog.get_logger(__name__)

# Reusable session for better performance
_session: aioboto3.Session | None = None


def get_session() -> aioboto3.Session:
    """Get or create aioboto3 session (singleton pattern)."""
    global _session
    if _session is None:
        _session = aioboto3.Session()
    return _session


async def download_pdf(bucket: str, key: str) -> bytes:
    """Download PDF from S3.

    Args:
        bucket: S3 bucket name
        key: Object key

    Returns:
        PDF file content as bytes

    Raises:
        ClientError: If S3 operation fails
    """
    logger.info("Downloading PDF from S3", bucket=bucket, key=key)

    session = get_session()
    async with session.client("s3", region_name=AWS_REGION) as s3:
        try:
            response = await s3.get_object(Bucket=bucket, Key=key)
            content = await response["Body"].read()

            logger.info(
                "PDF downloaded successfully",
                bucket=bucket,
                key=key,
                size_bytes=len(content),
            )
            return content

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "Failed to download PDF",
                bucket=bucket,
                key=key,
                error_code=error_code,
            )
            raise


async def upload_pdf(
    bucket: str,
    key: str,
    content: bytes,
    metadata: dict[str, str] | None = None,
) -> tuple[int, int]:
    """Upload PDF to S3 with ZIP compression.

    Args:
        bucket: S3 bucket name
        key: Object key (will be saved as .pdf.zip)
        content: PDF file content
        metadata: Optional metadata dictionary

    Returns:
        Tuple of (original_size, compressed_size)

    Raises:
        ClientError: If S3 operation fails
    """
    import io
    import zipfile

    original_size = len(content)

    # Compress with ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
        # Extract base filename and add to zip
        pdf_name = key.split('/')[-1].replace('.pdf.zip', '.pdf')
        zip_file.writestr(pdf_name, content)

    compressed_content = zip_buffer.getvalue()
    compressed_size = len(compressed_content)
    compression_ratio = (1 - compressed_size / original_size) * 100

    logger.info(
        "Uploading compressed PDF to S3",
        bucket=bucket,
        key=key,
        original_size=original_size,
        compressed_size=compressed_size,
        compression_ratio=f"{compression_ratio:.1f}%",
    )

    session = get_session()
    async with session.client("s3", region_name=AWS_REGION) as s3:
        try:
            upload_params: dict = {
                "Bucket": bucket,
                "Key": key,
                "Body": compressed_content,
                "ContentType": "application/zip",
            }

            if metadata is None:
                metadata = {}

            # Add compression info to metadata
            metadata.update({
                "original-size": str(original_size),
                "compressed-size": str(compressed_size),
                "compression-ratio": f"{compression_ratio:.1f}%",
            })

            upload_params["Metadata"] = metadata

            await s3.put_object(**upload_params)

            logger.info("Compressed PDF uploaded successfully", bucket=bucket, key=key)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "Failed to upload PDF",
                bucket=bucket,
                key=key,
                error_code=error_code,
            )
            raise

    return original_size, compressed_size


def generate_output_key(input_key: str, prefix: str = "anonymized") -> str:
    """Generate output key using ULID with /YYYY/mm structure and ZIP compression.

    Args:
        input_key: Input S3 key
        prefix: Prefix for output filename

    Returns:
        Generated S3 key with date structure: /YYYY/mm/anonymized_ULID.pdf.zip

    Examples:
        >>> generate_output_key("file.pdf")
        '2025/01/anonymized_01H2X....pdf.zip'
        >>> generate_output_key("path/to/file.pdf")
        '2025/01/anonymized_01H2X....pdf.zip'
    """
    from datetime import datetime

    ulid_str = ulid_lib.new().str
    now = datetime.utcnow()

    # Date-based path structure: /YYYY/mm
    year = now.year
    month = f"{now.month:02d}"
    date_path = f"{year}/{month}"

    # Filename with compression extension
    filename = f"{prefix}_{ulid_str}.pdf.zip"

    return f"{date_path}/{filename}"


async def list_bucket_stream(bucket: str, prefix: str = ""):
    """Stream PDFs from S3 bucket without loading all keys in memory.

    Args:
        bucket: S3 bucket name
        prefix: Optional prefix filter

    Yields:
        PDF keys from the bucket
    """
    session = get_session()
    async with session.client("s3", region_name=AWS_REGION) as s3:
        paginator = s3.get_paginator("list_objects_v2")

        async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.lower().endswith(".pdf"):
                    yield key


