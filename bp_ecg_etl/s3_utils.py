"""S3 utilities for PDF processing with connection pooling."""


import aioboto3
import structlog
from botocore.exceptions import ClientError
from ulid import ULID

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
) -> None:
    """Upload PDF to S3.

    Args:
        bucket: S3 bucket name
        key: Object key
        content: PDF file content
        metadata: Optional metadata dictionary

    Raises:
        ClientError: If S3 operation fails
    """
    logger.info("Uploading PDF to S3", bucket=bucket, key=key, size_bytes=len(content))

    session = get_session()
    async with session.client("s3", region_name=AWS_REGION) as s3:
        try:
            upload_params: dict = {
                "Bucket": bucket,
                "Key": key,
                "Body": content,
                "ContentType": "application/pdf",
            }

            if metadata:
                upload_params["Metadata"] = metadata

            await s3.put_object(**upload_params)

            logger.info("PDF uploaded successfully", bucket=bucket, key=key)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "Failed to upload PDF",
                bucket=bucket,
                key=key,
                error_code=error_code,
            )
            raise


def generate_output_key(input_key: str, prefix: str = "anonymized") -> str:
    """Generate output key using ULID for unique filename.

    Args:
        input_key: Input S3 key
        prefix: Prefix for output filename

    Returns:
        Generated S3 key with ULID

    Examples:
        >>> generate_output_key("file.pdf")
        'anonymized_01H2X..._pdf'
        >>> generate_output_key("path/to/file.pdf")
        'path/to/anonymized_01H2X..._pdf'
    """
    ulid_str = str(ULID())

    # Extract extension and directory
    if "." in input_key:
        _, ext = input_key.rsplit(".", 1)
    else:
        ext = "pdf"

    # Build filename
    filename = f"{prefix}_{ulid_str}.{ext}"

    # Preserve directory structure
    if "/" in input_key:
        directory = input_key.rsplit("/", 1)[0]
        return f"{directory}/{filename}"

    return filename


def generate_output_key_with_date(input_key: str, prefix: str = "anonymized") -> str:
    """Generate output key with Hive-style partitioning and compression.

    Args:
        input_key: Input S3 key
        prefix: Prefix for output filename

    Returns:
        Hive-partitioned key: year=YYYY/month=MM/day=DD/anonymized_ULID.pdf.gz

    Examples:
        >>> generate_output_key_with_date("file.pdf")
        'year=2025/month=01/day=15/anonymized_01HXX123.pdf.gz'
    """
    from datetime import datetime

    ulid_str = str(ULID())
    now = datetime.utcnow()

    # Hive-style partitioning
    year = f"year={now.year}"
    month = f"month={now.month:02d}"
    day = f"day={now.day:02d}"

    # Filename with compression extension
    filename = f"{prefix}_{ulid_str}.pdf.gz"

    return f"{year}/{month}/{day}/{filename}"


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


async def is_already_processed(input_key: str, output_bucket: str) -> bool:
    """Check if PDF was already processed (quick S3 head check).

    Args:
        input_key: Input PDF key
        output_bucket: Output bucket to check

    Returns:
        True if already processed, False otherwise
    """
    import os
    from datetime import datetime, timedelta

    base_name = os.path.basename(input_key).replace(".pdf", "").replace(".PDF", "")

    session = get_session()
    async with session.client("s3", region_name=AWS_REGION) as s3:
        # Search recent partitions (last 30 days) for optimization
        for days_ago in range(30):
            date = datetime.utcnow() - timedelta(days=days_ago)
            partition_prefix = f"year={date.year}/month={date.month:02d}/day={date.day:02d}/"

            try:
                response = await s3.list_objects_v2(
                    Bucket=output_bucket, Prefix=partition_prefix, MaxKeys=1000
                )

                for obj in response.get("Contents", []):
                    if base_name in obj["Key"] and obj["Key"].endswith(".pdf.gz"):
                        logger.debug(
                            "PDF already processed", input_key=input_key, existing_output=obj["Key"]
                        )
                        return True
            except ClientError:
                continue

        return False


async def upload_pdf_compressed(
    bucket: str,
    key: str,
    content: bytes,
    metadata: dict[str, str] | None = None,
) -> tuple[int, int]:
    """Upload PDF with GZIP compression.

    Args:
        bucket: S3 bucket name
        key: Object key (should end with .pdf.gz)
        content: PDF content to compress and upload
        metadata: Optional metadata

    Returns:
        Tuple of (original_size, compressed_size)
    """
    import gzip

    original_size = len(content)
    compressed_content = gzip.compress(content, compresslevel=9)
    compressed_size = len(compressed_content)

    if metadata is None:
        metadata = {}

    metadata.update(
        {
            "original-size": str(original_size),
            "compressed-size": str(compressed_size),
            "compression-ratio": f"{(1 - compressed_size / original_size) * 100:.2f}%",
        }
    )

    logger.info(
        "Uploading compressed PDF",
        bucket=bucket,
        key=key,
        original_size=original_size,
        compressed_size=compressed_size,
        ratio=metadata["compression-ratio"],
    )

    session = get_session()
    async with session.client("s3", region_name=AWS_REGION) as s3:
        try:
            await s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=compressed_content,
                ContentType="application/pdf",
                ContentEncoding="gzip",
                Metadata=metadata,
            )

            logger.info("Compressed PDF uploaded successfully", bucket=bucket, key=key)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "Failed to upload compressed PDF",
                bucket=bucket,
                key=key,
                error_code=error_code,
            )
            raise

    return original_size, compressed_size
