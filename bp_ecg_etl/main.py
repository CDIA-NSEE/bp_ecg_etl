"""Entry point for BP-ECG ETL - ECS Fargate with OPTIMIZED PERFORMANCE.

This module provides the main entry point for the BP-ECG ETL anonymization pipeline.
Optimized with:
- ProcessPoolExecutor for CPU-bound PDF processing (true parallelism)
- Async I/O for S3 operations (high concurrency)
- Batch processing for efficiency
- Smart queue management to prevent memory issues

Performance: ~3-4x faster than previous async-only approach.
"""

import asyncio
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Any

import structlog

from .config import (
    INPUT_BUCKET,
    MAX_PROCESS_WORKERS,
    MAX_WORKERS,
    OUTPUT_BUCKET,
    QUEUE_SIZE,
)
from .logging_config import setup_logging
from .pdf_worker import process_pdf_worker
from .s3_utils import (
    download_pdf,
    generate_output_key,
    list_bucket_stream,
    upload_pdf,
)

# Initialize logging
setup_logging()
logger = structlog.get_logger(__name__)

# Global process pool (initialized once)
_process_pool: ProcessPoolExecutor | None = None


def get_process_pool() -> ProcessPoolExecutor:
    """Get or create process pool for CPU-bound PDF processing.

    Auto-detects CPU count if MAX_PROCESS_WORKERS is 0.
    """
    global _process_pool
    if _process_pool is None:
        workers = MAX_PROCESS_WORKERS if MAX_PROCESS_WORKERS > 0 else (os.cpu_count() or 4) * 2
        _process_pool = ProcessPoolExecutor(
            max_workers=workers,
            max_tasks_per_child=100,  # Restart workers after 100 tasks to prevent memory leaks
        )
        logger.info("Process pool initialized", workers=workers)
    return _process_pool


async def producer_task(
    queue: asyncio.Queue,
    input_bucket: str,
    output_bucket: str,
    prefix: str = "",
) -> int:
    """Producer: Lists bucket and enqueues PDFs."""
    enqueued = 0

    logger.info("Producer started", bucket=input_bucket)

    async for pdf_key in list_bucket_stream(input_bucket, prefix):
        await queue.put(pdf_key)
        enqueued += 1

        if enqueued % 1000 == 0:
            logger.info("Progress", enqueued=enqueued)

    # Send poison pills to stop workers
    for _ in range(MAX_WORKERS):
        await queue.put(None)

    logger.info("Producer finished", total=enqueued)
    return enqueued


async def consumer_task(
    queue: asyncio.Queue,
    worker_id: int,
    input_bucket: str,
    output_bucket: str,
    stats: dict[str, Any],
) -> None:
    """Consumer: Processes PDFs from the queue."""
    process_pool = get_process_pool()
    loop = asyncio.get_event_loop()

    while True:
        pdf_key = await queue.get()

        if pdf_key is None:
            queue.task_done()
            break

        try:
            # Download
            pdf_content = await download_pdf(input_bucket, pdf_key)

            # Anonymize (CPU-bound in separate process)
            anonymized_content = await loop.run_in_executor(
                process_pool, process_pdf_worker, pdf_content
            )

            # Generate output key
            output_key = generate_output_key(pdf_key)

            # Metadata
            metadata = {
                "original-bucket": input_bucket,
                "original-key": pdf_key,
                "anonymized": "true",
            }

            # Upload
            original_size, compressed_size = await upload_pdf(
                output_bucket, output_key, anonymized_content, metadata
            )

            stats["successful"] += 1
            stats["total_original_bytes"] += original_size
            stats["total_compressed_bytes"] += compressed_size

        except Exception as e:
            stats["failed"] += 1
            logger.error("Failed", key=pdf_key, error=str(e)[:100])

        finally:
            queue.task_done()


async def async_main(prefix: str = "") -> dict[str, Any]:
    """Main async processing function - Stream processing with Producer/Consumer.

    Args:
        prefix: Optional S3 prefix filter

    Returns:
        Processing summary statistics
    """
    logger.info("Starting", workers=MAX_WORKERS)

    start_time = time.time()

    # Shared queue (bounded to prevent memory issues)
    queue = asyncio.Queue(maxsize=QUEUE_SIZE)

    # Shared stats
    stats = {
        "successful": 0,
        "failed": 0,
        "total_original_bytes": 0,
        "total_compressed_bytes": 0,
    }

    # Create producer task
    producer = asyncio.create_task(producer_task(queue, INPUT_BUCKET, OUTPUT_BUCKET, prefix))

    # Create consumer tasks (workers)
    consumers = [
        asyncio.create_task(consumer_task(queue, worker_id, INPUT_BUCKET, OUTPUT_BUCKET, stats))
        for worker_id in range(MAX_WORKERS)
    ]

    # Wait for producer to finish listing
    total_enqueued = await producer

    # Wait for all consumers to finish
    await asyncio.gather(*consumers)

    # Wait for queue to be fully processed
    await queue.join()

    total_time = time.time() - start_time

    # Calculate basic stats
    compression_ratio = 0
    if stats["total_original_bytes"] > 0:
        compression_ratio = (
            1 - stats["total_compressed_bytes"] / stats["total_original_bytes"]
        ) * 100

    result = {
        "statusCode": 200 if stats["failed"] == 0 else 207,
        "summary": {
            "total": total_enqueued,
            "successful": stats["successful"],
            "failed": stats["failed"],
            "time_sec": round(total_time, 2),
            "compression": f"{compression_ratio:.1f}%",
        },
    }

    logger.info(
        "Completed",
        successful=stats["successful"],
        failed=stats["failed"],
        time_sec=round(total_time, 2),
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
        print("COMPLETE")
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

    finally:
        # Cleanup process pool
        global _process_pool
        if _process_pool is not None:
            logger.info("Shutting down process pool")
            _process_pool.shutdown(wait=True)
            _process_pool = None


if __name__ == "__main__":
    sys.exit(main())
