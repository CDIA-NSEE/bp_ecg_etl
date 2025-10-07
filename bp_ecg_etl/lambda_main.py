"""Lambda handler for PDF anonymization with async processing."""

import asyncio
import json
import time
import urllib.parse
from typing import Any

import structlog

from .config import OUTPUT_BUCKET
from .pdf_anonymizer import anonymize_pdf
from .s3_utils import download_pdf, generate_output_key, upload_pdf

logger = structlog.get_logger(__name__)

# Constants
MAX_CONCURRENT_PDFS = 3  # Increased from 2 for better throughput


def parse_s3_event(event: dict[str, Any]) -> list[tuple[str, str]]:
    """Parse S3 event to extract PDF files.
    
    Args:
        event: Lambda S3 event
        
    Returns:
        List of (bucket, key) tuples for PDF files
    """
    records = event.get("Records", [])
    pdf_files: list[tuple[str, str]] = []
    
    for record in records:
        if record.get("eventSource") != "aws:s3":
            continue
            
        s3_info = record.get("s3", {})
        bucket = s3_info.get("bucket", {}).get("name")
        key = s3_info.get("object", {}).get("key")
        
        if bucket and key:
            key = urllib.parse.unquote_plus(key)
            if key.lower().endswith(".pdf"):
                pdf_files.append((bucket, key))
    
    return pdf_files


async def process_pdf_file(input_bucket: str, input_key: str) -> dict[str, Any]:
    """Process a single PDF file.
    
    Args:
        input_bucket: S3 bucket name
        input_key: S3 object key
        
    Returns:
        Processing result dictionary
    """
    start_time = time.time()
    
    try:
        # Download PDF
        pdf_content = await download_pdf(input_bucket, input_key)
        
        # Anonymize PDF (CPU-bound operation)
        anonymized_content = anonymize_pdf(pdf_content)
        
        # Generate output key and metadata
        output_key = generate_output_key(input_key)
        metadata = {
            "original-bucket": input_bucket,
            "original-key": input_key,
            "processing-timestamp": str(int(time.time())),
            "anonymized": "true",
        }
        
        # Upload anonymized PDF
        await upload_pdf(OUTPUT_BUCKET, output_key, anonymized_content, metadata)
        
        processing_time = time.time() - start_time
        
        logger.info(
            "PDF processed successfully",
            input_bucket=input_bucket,
            input_key=input_key,
            output_bucket=OUTPUT_BUCKET,
            output_key=output_key,
            processing_time_sec=round(processing_time, 3),
            input_size_bytes=len(pdf_content),
            output_size_bytes=len(anonymized_content),
        )
        
        return {
            "status": "success",
            "input_bucket": input_bucket,
            "input_key": input_key,
            "output_bucket": OUTPUT_BUCKET,
            "output_key": output_key,
            "processing_time": round(processing_time, 3),
            "input_size": len(pdf_content),
            "output_size": len(anonymized_content),
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        
        logger.error(
            "PDF processing failed",
            input_bucket=input_bucket,
            input_key=input_key,
            error=str(e),
            error_type=type(e).__name__,
            processing_time_sec=round(processing_time, 3),
        )
        
        return {
            "status": "error",
            "input_bucket": input_bucket,
            "input_key": input_key,
            "error": str(e),
            "error_type": type(e).__name__,
            "processing_time": round(processing_time, 3),
        }


async def async_lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Async Lambda handler for S3-triggered PDF anonymization.
    
    Args:
        event: Lambda S3 event
        context: Lambda context object
        
    Returns:
        Response dictionary with status code and body
    """
    logger.info("Lambda invoked", event_source="s3")

    try:
        # Parse S3 event
        pdf_files = parse_s3_event(event)

        if not pdf_files:
            logger.info("No PDF files in event")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "No PDF files to process"}),
            }

        logger.info("Processing PDFs", count=len(pdf_files))

        # Process files with concurrency limit
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_PDFS)

        async def process_with_limit(bucket: str, key: str) -> dict[str, Any]:
            async with semaphore:
                return await process_pdf_file(bucket, key)

        # Execute all tasks concurrently
        results = await asyncio.gather(
            *[process_with_limit(bucket, key) for bucket, key in pdf_files],
            return_exceptions=True,
        )

        # Aggregate results
        successful = 0
        failed = 0
        processed_results: list[dict[str, Any]] = []

        for result in results:
            if isinstance(result, BaseException):
                # Handle exceptions from gather
                result_dict: dict[str, Any] = {
                    "status": "error",
                    "error": str(result),
                    "error_type": type(result).__name__,
                }
                failed += 1
            else:
                # Handle successful dict results
                result_dict = result
                if result_dict.get("status") == "success":
                    successful += 1
                else:
                    failed += 1
            
            processed_results.append(result_dict)

        logger.info(
            "Processing completed",
            total=len(pdf_files),
            successful=successful,
            failed=failed,
        )

        # Return 207 (Multi-Status) if any failures
        status_code = 200 if failed == 0 else 207

        return {
            "statusCode": status_code,
            "body": json.dumps(
                {
                    "message": "PDF processing completed",
                    "summary": {
                        "total_files": len(pdf_files),
                        "successful": successful,
                        "failed": failed,
                    },
                    "results": processed_results,
                }
            ),
        }

    except Exception as e:
        logger.error("Lambda failed", error=str(e), error_type=type(e).__name__)
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": "Internal server error", "message": str(e)}
            ),
        }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Main Lambda handler entry point.
    
    Args:
        event: Lambda S3 event
        context: Lambda context object
        
    Returns:
        Response dictionary with status code and body
    """
    return asyncio.run(async_lambda_handler(event, context))
