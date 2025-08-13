"""Simple S3 utilities for PDF processing."""

import asyncio
import aioboto3
import structlog
from botocore.exceptions import ClientError
from ulid import new
from .config import AWS_REGION

logger = structlog.get_logger(__name__)


async def download_pdf(bucket: str, key: str) -> bytes:
    """Download PDF from S3."""
    logger.info("Downloading PDF from S3", bucket=bucket, key=key)

    session = aioboto3.Session()
    async with session.client("s3", region_name=AWS_REGION) as s3:
        try:
            response = await s3.get_object(Bucket=bucket, Key=key)
            content = await response["Body"].read()

            logger.info(
                "Successfully downloaded PDF", bucket=bucket, key=key, size=len(content)
            )
            return content

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "Failed to download PDF", bucket=bucket, key=key, error=error_code
            )
            raise


async def upload_pdf(
    bucket: str, key: str, content: bytes, metadata: dict | None = None
) -> None:
    """Upload PDF to S3."""
    logger.info("Uploading PDF to S3", bucket=bucket, key=key, size=len(content))

    session = aioboto3.Session()
    async with session.client("s3", region_name=AWS_REGION) as s3:
        try:
            upload_params = {
                "Bucket": bucket,
                "Key": key,
                "Body": content,
                "ContentType": "application/pdf",
            }

            if metadata:
                upload_params["Metadata"] = metadata

            await s3.put_object(**upload_params)

            logger.info("Successfully uploaded PDF", bucket=bucket, key=key)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "Failed to upload PDF", bucket=bucket, key=key, error=error_code
            )
            raise


def generate_output_key(input_key: str, prefix: str = "anonymized") -> str:
    """Generate output key using ULID for unique filename."""
    # Generate a new ULID for unique filename
    ulid = str(new())

    # Extract file extension from input key
    if "." in input_key:
        _, ext = input_key.rsplit(".", 1)
        filename = f"{prefix}_{ulid}.{ext}"
    else:
        filename = f"{prefix}_{ulid}.pdf"  # Default to PDF if no extension

    # Preserve directory structure if present
    if "/" in input_key:
        path, _ = input_key.rsplit("/", 1)
        return f"{path}/{filename}"
    else:
        return filename
