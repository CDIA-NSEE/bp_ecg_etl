"""Simple S3 utilities for PDF processing."""

import io
import zipfile

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

            logger.info("Successfully downloaded PDF", bucket=bucket, key=key, size=len(content))
            return content

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error("Failed to download PDF", bucket=bucket, key=key, error=error_code)
            raise


async def upload_pdf(bucket: str, key: str, content: bytes, metadata: dict | None = None) -> None:
    """Upload PDF to S3 with zip compression (saves as .pdf.zip)."""
    original_size = len(content)
    # Comprimir com zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
        # Extrair nome base do arquivo (remover path se houver)
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

    session = aioboto3.Session()
    async with session.client("s3", region_name=AWS_REGION) as s3:
        try:
            upload_params = {
                "Bucket": bucket,
                "Key": key,
                "Body": compressed_content,
                "ContentType": "application/zip",
            }

            if metadata:
                # Adiciona info de compressão aos metadados
                upload_params["Metadata"] = {
                    **metadata,
                    "original-size": str(original_size),
                    "compressed-size": str(compressed_size),
                }

            await s3.put_object(**upload_params)

            logger.info("Successfully uploaded compressed PDF", bucket=bucket, key=key)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error("Failed to upload PDF", bucket=bucket, key=key, error=error_code)
            raise



def generate_output_key(input_key: str, prefix: str = "anonymized") -> str:
    """Generate output key using ULID for unique filename (.pdf.zip)."""
    # Generate a new ULID for unique filename
    ulid = str(new())

    # Sempre gera .pdf.zip (comprimido)
    filename = f"{prefix}_{ulid}.pdf.zip"

    # Preserve directory structure if present
    if "/" in input_key:
        path, _ = input_key.rsplit("/", 1)
        return f"{path}/{filename}"
    else:
        return filename


