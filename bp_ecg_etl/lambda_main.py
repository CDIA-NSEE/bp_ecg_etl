"""Simple Lambda handler for PDF anonymization."""

import asyncio
import json
import time
import urllib.parse
import structlog

from . import config
from .s3_utils import download_pdf, upload_pdf, generate_output_key
from .pdf_anonymizer import anonymize_pdf

logger = structlog.get_logger(__name__)


def parse_s3_event(event):
    """Parse S3 event to extract bucket and object keys."""
    records = event.get('Records', [])
    pdf_files = []
    
    for record in records:
        if record.get('eventSource') == 'aws:s3':
            s3_info = record.get('s3', {})
            bucket = s3_info.get('bucket', {}).get('name')
            key = s3_info.get('object', {}).get('key')
            
            if bucket and key:
                # URL decode the key
                key = urllib.parse.unquote_plus(key)
                
                # Only process PDF files
                if key.lower().endswith('.pdf'):
                    pdf_files.append((bucket, key))
    
    return pdf_files


async def process_pdf_file(input_bucket: str, input_key: str):
    """Process a single PDF file."""
    start_time = time.time()
    
    try:
        # Download PDF
        pdf_content = await download_pdf(input_bucket, input_key)
        
        # Anonymize PDF
        anonymized_content = anonymize_pdf(pdf_content)
        
        # Generate output key and upload
        output_key = generate_output_key(input_key)
        metadata = {
            'original-bucket': input_bucket,
            'original-key': input_key,
            'processing-timestamp': str(int(time.time())),
            'anonymized': 'true'
        }
        
        await upload_pdf(config.OUTPUT_BUCKET, output_key, anonymized_content, metadata)
        
        processing_time = time.time() - start_time
        
        logger.info(
            "Successfully processed PDF",
            input_bucket=input_bucket,
            input_key=input_key,
            output_bucket=config.OUTPUT_BUCKET,
            output_key=output_key,
            processing_time=round(processing_time, 3),
            input_size=len(pdf_content),
            output_size=len(anonymized_content)
        )
        
        return {
            'status': 'success',
            'input_bucket': input_bucket,
            'input_key': input_key,
            'output_bucket': config.OUTPUT_BUCKET,
            'output_key': output_key,
            'processing_time': round(processing_time, 3),
            'input_size': len(pdf_content),
            'output_size': len(anonymized_content)
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        
        logger.error(
            "Failed to process PDF",
            input_bucket=input_bucket,
            input_key=input_key,
            error=str(e),
            processing_time=round(processing_time, 3)
        )
        
        return {
            'status': 'error',
            'input_bucket': input_bucket,
            'input_key': input_key,
            'error': str(e),
            'processing_time': round(processing_time, 3)
        }


async def async_lambda_handler(event, context):
    """Async Lambda handler."""
    logger.info("Lambda function started", event=event)
    
    try:
        # Parse S3 event
        pdf_files = parse_s3_event(event)
        
        if not pdf_files:
            logger.info("No PDF files found in event")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No PDF files to process'})
            }
        
        logger.info("Processing PDF files", count=len(pdf_files))
        
        # Process files (with limited concurrency for Lambda)
        semaphore = asyncio.Semaphore(2)  # Limit concurrent processing
        
        async def process_with_semaphore(bucket, key):
            async with semaphore:
                return await process_pdf_file(bucket, key)
        
        # Execute all processing tasks
        tasks = [process_with_semaphore(bucket, key) for bucket, key in pdf_files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes and failures
        successful = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'success')
        failed = len(results) - successful
        
        logger.info(
            "Lambda processing completed",
            total_files=len(results),
            successful=successful,
            failed=failed
        )
        
        return {
            'statusCode': 200 if failed == 0 else 207,  # 207 = Multi-Status
            'body': json.dumps({
                'message': 'PDF processing completed',
                'summary': {
                    'total_files': len(results),
                    'successful': successful,
                    'failed': failed
                },
                'results': results
            }, indent=2)
        }
        
    except Exception as e:
        logger.error("Lambda function failed", error=str(e))
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }


def lambda_handler(event, context):
    """Main Lambda handler entry point."""
    return asyncio.run(async_lambda_handler(event, context))
