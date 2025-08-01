"""S3 utility functions with retry logic."""

from typing import List, AsyncGenerator
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from ..types import S3Client, Logger

logger: Logger = structlog.get_logger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def download_from_s3(s3_client: S3Client, bucket: str, key: str) -> bytes:
    """Download file from S3 with retry logic.
    
    Args:
        s3_client: Async S3 client
        bucket: S3 bucket name
        key: S3 object key
        
    Returns:
        File content as bytes
        
    Raises:
        Exception: If download fails after retries
    """
    try:
        logger.info("Downloading from S3", bucket=bucket, key=key)
        response = await s3_client.get_object(Bucket=bucket, Key=key)
        content = await response['Body'].read()
        logger.info("Successfully downloaded from S3", bucket=bucket, key=key, size=len(content))
        return content
    except Exception as e:
        logger.error("Failed to download from S3", bucket=bucket, key=key, error=str(e))
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def upload_to_s3(
    s3_client: S3Client, 
    bucket: str, 
    key: str, 
    data: bytes, 
    content_type: str = "application/octet-stream"
) -> None:
    """Upload data to S3 with retry logic.
    
    Args:
        s3_client: Async S3 client
        bucket: S3 bucket name
        key: S3 object key
        data: Data to upload
        content_type: MIME type of the data
        
    Raises:
        Exception: If upload fails after retries
    """
    try:
        logger.info("Uploading to S3", bucket=bucket, key=key, size=len(data))
        await s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type
        )
        logger.info("Successfully uploaded to S3", bucket=bucket, key=key)
    except Exception as e:
        logger.error("Failed to upload to S3", bucket=bucket, key=key, error=str(e))
        raise


async def list_pdf_keys(
    s3_client: S3Client, 
    bucket: str, 
    prefix: str, 
    start_after: str = ""
) -> AsyncGenerator[List[str], None]:
    """List PDF keys from S3 with pagination.
    
    Args:
        s3_client: Async S3 client
        bucket: S3 bucket name
        prefix: Key prefix to filter objects
        start_after: Key to start listing after (for pagination)
        
    Yields:
        Lists of PDF object keys
    """
    try:
        logger.info("Listing PDF keys from S3", bucket=bucket, prefix=prefix, start_after=start_after)
        
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(
            Bucket=bucket,
            Prefix=prefix,
            StartAfter=start_after
        )
        
        async for page in page_iterator:
            if 'Contents' in page:
                pdf_keys = [
                    obj['Key'] for obj in page['Contents'] 
                    if obj['Key'].lower().endswith('.pdf')
                ]
                if pdf_keys:
                    logger.info("Found PDF keys", count=len(pdf_keys))
                    yield pdf_keys
                    
    except Exception as e:
        logger.error("Failed to list PDF keys", bucket=bucket, prefix=prefix, error=str(e))
        raise
