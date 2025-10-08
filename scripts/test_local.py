#!/usr/bin/env python3
"""Script para testar o pipeline BP-ECG ETL localmente usando LocalStack."""

import sys
from pathlib import Path

import boto3
import structlog

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bp_ecg_etl.config import INPUT_BUCKET, OUTPUT_BUCKET
from bp_ecg_etl.logging_config import setup_logging
from bp_ecg_etl.pdf_anonymizer import anonymize_pdf
from bp_ecg_etl.s3_utils import generate_output_key_with_date

# Setup logging
setup_logging()
logger = structlog.get_logger(__name__)

# LocalStack endpoint
LOCALSTACK_ENDPOINT = "http://localhost:4566"


def get_localstack_s3_client():
    """Create S3 client for LocalStack."""
    return boto3.client(
        's3',
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )


def test_local_pipeline(pdf_path: str) -> None:
    """Test the pipeline locally with a PDF file.
    
    Args:
        pdf_path: Path to PDF file to process
    """
    pdf_file = Path(pdf_path)
    
    if not pdf_file.exists():
        logger.error("PDF file not found", path=pdf_path)
        sys.exit(1)
    
    logger.info("Starting local pipeline test", pdf_file=pdf_file.name)
    
    # Read PDF
    with open(pdf_file, 'rb') as f:
        pdf_content = f.read()
    
    logger.info("PDF loaded", size_bytes=len(pdf_content))
    
    # Anonymize
    try:
        anonymized_content = anonymize_pdf(pdf_content)
        logger.info("PDF anonymized", 
                   original_size=len(pdf_content),
                   anonymized_size=len(anonymized_content),
                   compression_ratio=f"{len(anonymized_content)/len(pdf_content)*100:.1f}%")
    except Exception as e:
        logger.error("Anonymization failed", error=str(e))
        sys.exit(1)
    
    # Upload to LocalStack S3
    s3_client = get_localstack_s3_client()
    
    # Upload original to input bucket
    input_key = f"test/{pdf_file.name}"
    try:
        s3_client.put_object(
            Bucket=INPUT_BUCKET,
            Key=input_key,
            Body=pdf_content
        )
        logger.info("Uploaded to input bucket", bucket=INPUT_BUCKET, key=input_key)
    except Exception as e:
        logger.error("Failed to upload to input bucket", error=str(e))
        sys.exit(1)
    
    # Upload anonymized to output bucket
    output_key = generate_output_key_with_date(input_key)
    try:
        s3_client.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=output_key,
            Body=anonymized_content
        )
        logger.info("Uploaded to output bucket", bucket=OUTPUT_BUCKET, key=output_key)
    except Exception as e:
        logger.error("Failed to upload to output bucket", error=str(e))
        sys.exit(1)
    
    # Save local copy
    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"anonymized_{pdf_file.name}"
    
    with open(output_file, 'wb') as f:
        f.write(anonymized_content)
    
    logger.info("Test completed successfully", output_file=str(output_file))
    
    print("\n✅ Pipeline test completed!")
    print(f"📄 Original: {pdf_file} ({len(pdf_content):,} bytes)")
    print(f"📄 Anonymized: {output_file} ({len(anonymized_content):,} bytes)")
    print(f"📊 Compression: {len(anonymized_content)/len(pdf_content)*100:.1f}%")
    print("\n🪣 S3 LocalStack:")
    print(f"   Input: s3://{INPUT_BUCKET}/{input_key}")
    print(f"   Output: s3://{OUTPUT_BUCKET}/{output_key}")


def list_buckets():
    """List all buckets in LocalStack."""
    s3_client = get_localstack_s3_client()
    try:
        response = s3_client.list_buckets()
        print("\n🪣 Buckets disponíveis:")
        for bucket in response['Buckets']:
            print(f"   - {bucket['Name']}")
    except Exception as e:
        logger.error("Failed to list buckets", error=str(e))


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_local.py <pdf_file>")
        print("       python scripts/test_local.py --list-buckets")
        sys.exit(1)
    
    if sys.argv[1] == "--list-buckets":
        list_buckets()
    else:
        test_local_pipeline(sys.argv[1])


if __name__ == "__main__":
    main()
