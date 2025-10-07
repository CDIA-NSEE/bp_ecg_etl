"""Entry point for BP-ECG ETL - ECS Fargate.

This module provides the main entry point for the BP-ECG ETL anonymization pipeline.
Runs as ECS Fargate task with long-running stream processing.
"""

import asyncio
import json
import sys
import time
from typing import Any

import structlog

from .config import (
    INPUT_BUCKET,
    MAX_WORKERS,
    OUTPUT_BUCKET,
    QUEUE_SIZE,
)
from .logging_config import setup_logging
from .pdf_anonymizer import anonymize_pdf
from .s3_utils import (
    download_pdf,
    generate_output_key_with_date,
    is_already_processed,
    list_bucket_stream,
    upload_pdf_compressed,
)

# Initialize logging
setup_logging()
logger = structlog.get_logger(__name__)


async def producer_task(
    queue: asyncio.Queue,
    input_bucket: str,
    output_bucket: str,
    prefix: str = "",
) -> int:
    """Producer: Lists bucket and enqueues unprocessed PDFs.
    
    Args:
        queue: asyncio.Queue to put PDF keys
        input_bucket: Source S3 bucket
        output_bucket: Destination S3 bucket (for checking processed)
        prefix: Optional S3 prefix filter
        
    Returns:
        Total number of PDFs enqueued
    """
    enqueued = 0
    checked = 0
    
    logger.info("Producer started", bucket=input_bucket, prefix=prefix, max_workers=MAX_WORKERS)
    
    async for pdf_key in list_bucket_stream(input_bucket, prefix):
        checked += 1
        
        # Check if already processed
        if await is_already_processed(pdf_key, output_bucket):
            logger.debug("PDF already processed, skipping", key=pdf_key)
            continue
        
        # Enqueue for processing
        await queue.put(pdf_key)
        enqueued += 1
        
        # Progress log
        if enqueued % 100 == 0:
            logger.info(
                "Producer progress",
                checked=checked,
                enqueued=enqueued,
                queue_size=queue.qsize(),
            )
    
    # Send poison pills to stop workers
    for _ in range(MAX_WORKERS):
        await queue.put(None)
    
    logger.info(
        "Producer finished",
        total_checked=checked,
        total_enqueued=enqueued,
        already_processed=checked - enqueued,
    )
    
    return enqueued


async def consumer_task(
    queue: asyncio.Queue,
    worker_id: int,
    input_bucket: str,
    output_bucket: str,
    stats: dict[str, Any],
) -> None:
    """Consumer: Processes PDFs from the queue.
    
    Args:
        queue: asyncio.Queue to get PDF keys from
        worker_id: Unique worker identifier
        input_bucket: Source S3 bucket
        output_bucket: Destination S3 bucket
        stats: Shared stats dictionary
    """
    processed = 0
    
    logger.info("Consumer started", worker_id=worker_id)
    
    while True:
        # Get next PDF from queue
        pdf_key = await queue.get()
        
        # Poison pill = stop
        if pdf_key is None:
            queue.task_done()
            break
        
        try:
            start_time = time.time()
            
            # Download
            pdf_content = await download_pdf(input_bucket, pdf_key)
            
            # Anonymize
            anonymized_content = anonymize_pdf(pdf_content)
            
            # Generate Hive-partitioned output key
            output_key = generate_output_key_with_date(pdf_key)
            
            # Metadata
            metadata = {
                "original-bucket": input_bucket,
                "original-key": pdf_key,
                "processing-timestamp": str(int(time.time())),
                "anonymized": "true",
                "worker-id": str(worker_id),
            }
            
            # Upload with compression
            original_size, compressed_size = await upload_pdf_compressed(
                output_bucket, output_key, anonymized_content, metadata
            )
            
            processing_time = time.time() - start_time
            processed += 1
            
            # Update shared stats
            stats["successful"] += 1
            stats["total_original_bytes"] += original_size
            stats["total_compressed_bytes"] += compressed_size
            
            logger.info(
                "PDF processed",
                worker_id=worker_id,
                input_key=pdf_key,
                output_key=output_key,
                processing_time_sec=round(processing_time, 2),
                compression_ratio=f"{(1 - compressed_size/original_size)*100:.1f}%",
                worker_total=processed,
            )
            
        except Exception as e:
            stats["failed"] += 1
            logger.error(
                "PDF processing failed",
                worker_id=worker_id,
                input_key=pdf_key,
                error=str(e),
                error_type=type(e).__name__,
            )
        
        finally:
            queue.task_done()
    
    logger.info("Consumer finished", worker_id=worker_id, total_processed=processed)


async def async_main(prefix: str = "") -> dict[str, Any]:
    """Main async processing function - Stream processing with Producer/Consumer.
    
    Args:
        prefix: Optional S3 prefix filter
        
    Returns:
        Processing summary statistics
    """
    logger.info(
        "BP-ECG ETL started - Stream processing mode",
        input_bucket=INPUT_BUCKET,
        output_bucket=OUTPUT_BUCKET,
        max_workers=MAX_WORKERS,
        queue_size=QUEUE_SIZE,
    )
    
    start_time = time.time()
    
    # Shared queue (bounded to prevent memory issues)
    queue = asyncio.Queue(maxsize=QUEUE_SIZE)
    
    # Shared stats dictionary
    stats = {
        "successful": 0,
        "failed": 0,
        "total_original_bytes": 0,
        "total_compressed_bytes": 0,
    }
    
    # Create producer task
    producer = asyncio.create_task(
        producer_task(queue, INPUT_BUCKET, OUTPUT_BUCKET, prefix)
    )
    
    # Create consumer tasks (workers)
    consumers = [
        asyncio.create_task(
            consumer_task(queue, worker_id, INPUT_BUCKET, OUTPUT_BUCKET, stats)
        )
        for worker_id in range(MAX_WORKERS)
    ]
    
    # Wait for producer to finish listing
    total_enqueued = await producer
    
    # Wait for all consumers to finish
    await asyncio.gather(*consumers)
    
    # Wait for queue to be fully processed
    await queue.join()
    
    total_time = time.time() - start_time
    
    # Calculate statistics
    avg_compression = 0
    if stats["total_original_bytes"] > 0:
        avg_compression = (
            1 - stats["total_compressed_bytes"] / stats["total_original_bytes"]
        ) * 100
    
    result = {
        "statusCode": 200 if stats["failed"] == 0 else 207,
        "summary": {
            "total_enqueued": total_enqueued,
            "successful": stats["successful"],
            "failed": stats["failed"],
            "total_time_seconds": round(total_time, 2),
        },
        "compression_stats": {
            "avg_compression_ratio": f"{avg_compression:.1f}%",
            "total_saved_bytes": stats["total_original_bytes"]
            - stats["total_compressed_bytes"],
        },
    }
    
    logger.info(
        "Stream processing completed",
        total_enqueued=total_enqueued,
        successful=stats["successful"],
        failed=stats["failed"],
        total_time_sec=round(total_time, 2),
        avg_compression_ratio=f"{avg_compression:.1f}%",
    )
    
    return result


def main() -> int:
    """ECS Fargate entry point - runs until all PDFs are processed.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        result = asyncio.run(async_main())
        
        print("\n" + "=" * 60)
        print("PROCESSING COMPLETE")
        print("=" * 60)
        print(json.dumps(result, indent=2))
        print("=" * 60)
        
        # Exit with error if any failures
        if result["summary"]["failed"] > 0:
            logger.warning(
                "Processing completed with failures",
                failed=result["summary"]["failed"],
            )
            return 1
        
        return 0
        
    except Exception as e:
        logger.error("Fatal error in main", error=str(e), error_type=type(e).__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
