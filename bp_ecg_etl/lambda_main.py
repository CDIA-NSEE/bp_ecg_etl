"""Simple Lambda handler for PDF anonymization."""

import asyncio
import json
import time
import urllib.parse
import structlog

from .s3_utils import download_pdf, upload_pdf, generate_output_key
from .pdf_anonymizer import anonymize_pdf
from .config import OUTPUT_BUCKET

logger = structlog.get_logger(__name__)


def parse_s3_event(event):
    """Parse S3 event to extract PDF files."""
    records = event.get("Records", [])
    pdf_files = []
    
    for record in records:
        if record.get("eventSource") == "aws:s3":
            s3_info = record.get("s3", {})
            bucket = s3_info.get("bucket", {}).get("name")
            key = s3_info.get("object", {}).get("key")
            
            if bucket and key:
                key = urllib.parse.unquote_plus(key)
                if key.lower().endswith(".pdf"):
                    pdf_files.append((bucket, key))
    
    return pdf_files


async def process_pdf_file(input_bucket, input_key):
    """Process a single PDF file."""
    start_time = time.time()
    
    try:
        # Download PDF
        pdf_content = await download_pdf(input_bucket, input_key)
        
        # Anonymize PDF
        anonymized_content = anonymize_pdf(pdf_content)
        
        # Upload anonymized PDF
        output_key = generate_output_key(input_key)
        metadata = {
            "original-bucket": input_bucket,
            "original-key": input_key,
            "processing-timestamp": str(int(time.time())),
            "anonymized": "true"
        }
        
        await upload_pdf(OUTPUT_BUCKET, output_key, anonymized_content, metadata)
        
        processing_time = time.time() - start_time
        
        logger.info(
            "PDF processed successfully",
            input_bucket=input_bucket,
            input_key=input_key,
            output_bucket=OUTPUT_BUCKET,
            output_key=output_key,
            processing_time=round(processing_time, 3),
            input_size=len(pdf_content),
            output_size=len(anonymized_content)
        )
        
        return {
            "status": "success",
            "input_bucket": input_bucket,
            "input_key": input_key,
            "output_bucket": OUTPUT_BUCKET,
            "output_key": output_key,
            "processing_time": round(processing_time, 3),
            "input_size": len(pdf_content),
            "output_size": len(anonymized_content)
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        
        logger.error(
            "PDF processing failed",
            input_bucket=input_bucket,
            input_key=input_key,
            error=str(e),
            processing_time=round(processing_time, 3)
        )
        
        return {
            "status": "error",
            "input_bucket": input_bucket,
            "input_key": input_key,
            "error": str(e),
            "processing_time": round(processing_time, 3)
        }


async def async_lambda_handler(event, context):
    """Simple async Lambda handler."""
    logger.info("Lambda function started", s3_event=event)

    try:
        # Parse S3 event
        pdf_files = parse_s3_event(event)

        if not pdf_files:
            logger.info("No PDF files found in event")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "No PDF files to process"})
            }

        logger.info("Processing PDF files", count=len(pdf_files))

        # Process files with limited concurrency
        semaphore = asyncio.Semaphore(2)

        async def process_with_semaphore(bucket, key):
            async with semaphore:
                return await process_pdf_file(bucket, key)

        # Execute all processing tasks
        tasks = [process_with_semaphore(bucket, key) for bucket, key in pdf_files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results = []
        successful = 0
        failed = 0

        for result in results:
            if isinstance(result, Exception):
                result_dict = {
                    "status": "error",
                    "error": str(result),
                    "error_type": type(result).__name__
                }
                failed += 1
            else:
                result_dict = result
                if isinstance(result_dict, dict) and result_dict.get("status") == "success":
                    successful += 1
                else:
                    failed += 1
            
            processed_results.append(result_dict)

        logger.info(
            "Lambda processing completed",
            total_files=len(pdf_files),
            successful=successful,
            failed=failed
        )

        return {
            "statusCode": 200 if failed == 0 else 207,
            "body": json.dumps({
                "message": "PDF processing completed",
                "summary": {
                    "total_files": len(pdf_files),
                    "successful": successful,
                    "failed": failed
                },
                "results": processed_results
            }, indent=2)
        }

    except Exception as e:
        logger.error("Lambda function failed", error=str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error", "message": str(e)})
        }


def lambda_handler(event, context):
    """Main Lambda handler entry point."""
    return asyncio.run(async_lambda_handler(event, context))
