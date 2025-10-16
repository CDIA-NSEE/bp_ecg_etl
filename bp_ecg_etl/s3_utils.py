"""S3 utilities for PDF processing with optimized connection pooling."""

import asyncio
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import aioboto3
import structlog
import ulid as ulid_lib
from botocore.config import Config
from botocore.exceptions import ClientError

from .config import (
    AWS_REGION,
    S3_CONNECT_TIMEOUT,
    S3_MAX_POOL_CONNECTIONS,
    S3_READ_TIMEOUT,
    ZIP_COMPRESSION_LEVEL,
)

logger = structlog.get_logger(__name__)

# Reusable session with optimized connection pooling
_session: aioboto3.Session | None = None
_thread_pool: ThreadPoolExecutor | None = None

# Optimized boto3 config for high throughput
_boto_config = Config(
    max_pool_connections=S3_MAX_POOL_CONNECTIONS,
    connect_timeout=S3_CONNECT_TIMEOUT,
    read_timeout=S3_READ_TIMEOUT,
    retries={'max_attempts': 3, 'mode': 'adaptive'},
    tcp_keepalive=True,
)


def get_session() -> aioboto3.Session:
    """Get or create aioboto3 session (singleton pattern)."""
    global _session
    if _session is None:
        _session = aioboto3.Session()
    return _session


def get_thread_pool() -> ThreadPoolExecutor:
    """Get or create thread pool for CPU-bound compression operations."""
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="zip-compress")
    return _thread_pool


async def download_pdf(bucket: str, key: str) -> bytes:
    """Download PDF from S3 with optimized connection pooling.

    Args:
        bucket: S3 bucket name
        key: Object key

    Returns:
        PDF file content as bytes

    Raises:
        ClientError: If S3 operation fails
    """
    session = get_session()
    async with session.client("s3", region_name=AWS_REGION, config=_boto_config) as s3:
        try:
            response = await s3.get_object(Bucket=bucket, Key=key)
            content = await response["Body"].read()

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


def _compress_pdf_sync(content: bytes, key: str) -> tuple[bytes, int, int, float]:
    """Synchronous ZIP compression (runs in thread pool).

    Returns:
        Tuple of (compressed_content, original_size, compressed_size, compression_ratio)
    """
    original_size = len(content)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=ZIP_COMPRESSION_LEVEL) as zip_file:
        pdf_name = key.split('/')[-1].replace('.pdf.zip', '.pdf')
        zip_file.writestr(pdf_name, content)

    compressed_content = zip_buffer.getvalue()
    compressed_size = len(compressed_content)
    compression_ratio = (1 - compressed_size / original_size) * 100

    return compressed_content, original_size, compressed_size, compression_ratio


async def upload_pdf(
    bucket: str,
    key: str,
    content: bytes,
    metadata: dict[str, str] | None = None,
) -> tuple[int, int]:
    """Upload PDF to S3 with async ZIP compression.

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
    # Compress in thread pool (CPU-bound operation)
    loop = asyncio.get_event_loop()
    thread_pool = get_thread_pool()
    compressed_content, original_size, compressed_size, compression_ratio = await loop.run_in_executor(
        thread_pool, _compress_pdf_sync, content, key
    )

    session = get_session()
    async with session.client("s3", region_name=AWS_REGION, config=_boto_config) as s3:
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
    """
    ulid_str = ulid_lib.new().str
    now = datetime.utcnow()

    # Date-based path structure: /YYYY/mm
    year = now.year
    month = f"{now.month:02d}"
    date_path = f"{year}/{month}"

    filename = f"{prefix}_{ulid_str}.pdf.zip"

    return f"{date_path}/{filename}"


async def list_bucket_stream(bucket: str, prefix: str = ""):
    """Stream PDFs from S3 bucket with optimized pagination.

    Args:
        bucket: S3 bucket name
        prefix: Optional prefix filter

    Yields:
        PDF keys from the bucket
    """
    session = get_session()
    async with session.client("s3", region_name=AWS_REGION, config=_boto_config) as s3:
        paginator = s3.get_paginator("list_objects_v2")

        async for page in paginator.paginate(Bucket=bucket, Prefix=prefix, PaginationConfig={'PageSize': 1000}):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.lower().endswith(".pdf"):
                    yield key


async def batch_upload_pdfs(
    bucket: str,
    items: list[tuple[str, bytes, dict[str, str]]],
) -> list[tuple[int, int]]:
    """Batch upload multiple PDFs to S3 with parallel compression.

    Args:
        bucket: S3 bucket name
        items: List of (key, content, metadata) tuples

    Returns:
        List of (original_size, compressed_size) tuples
    """
    results = await asyncio.gather(
        *[upload_pdf(bucket, key, content, metadata) for key, content, metadata in items],
        return_exceptions=True
    )

    # Filter out exceptions and return successful results
    valid_results: list[tuple[int, int]] = []
    for r in results:
        if not isinstance(r, Exception):
            valid_results.append(r)
    return valid_results


