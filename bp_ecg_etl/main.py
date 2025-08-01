"""BP-ECG ETL main entry point with improved typing and modular structure."""

import asyncio
import json
import os
import sys
import time
from typing import Dict, Any, Optional

import aioboto3
import boto3
import polars as pl
import structlog
from aws_lambda_typing.events import S3Event
from aws_lambda_typing.context import Context

from .types import (
    LambdaClient, 
    Logger, 
    ProcessingResult, 
    BatchResult, 
    ProcessingStatus
)
from .core import list_pdf_keys, process_single_pdf
from .config import get_settings

# Setup structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger: Logger = structlog.get_logger(__name__)


async def run_batch(start_after: Optional[str] = None, batch_id: int = 0) -> Dict[str, Any]:
    """Process a batch of PDFs.
    
    Args:
        start_after: S3 key to start listing from (for pagination)
        batch_id: Unique identifier for this batch
        
    Returns:
        Dictionary containing batch processing results
    """
    settings = get_settings()
    start_time = time.time()
    
    logger.info("Starting batch processing", 
                batch_id=batch_id, start_after=start_after, 
                batch_size=settings.BATCH_SIZE)
    
    try:
        # Initialize AWS clients
        session = aioboto3.Session()
        async with session.client('s3') as s3_client:
            
            # Get PDF keys to process
            pdf_keys = []
            async for key_batch in list_pdf_keys(
                s3_client, 
                settings.SOURCE_BUCKET, 
                settings.PDF_PREFIX, 
                start_after or ""
            ):
                pdf_keys.extend(key_batch)
                if len(pdf_keys) >= settings.BATCH_SIZE:
                    break
            
            if not pdf_keys:
                logger.info("No PDFs found to process", batch_id=batch_id)
                return BatchResult(
                    batch_id=batch_id,
                    processed=0,
                    success=0,
                    errors=0,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                    status=ProcessingStatus.DONE
                ).to_dict()
            
            # Limit to batch size
            pdf_keys = pdf_keys[:settings.BATCH_SIZE]
            logger.info("Processing PDF batch", batch_id=batch_id, pdf_count=len(pdf_keys))
            
            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(settings.CONCURRENCY)
            
            async def process_with_semaphore(pdf_key: str) -> ProcessingResult:
                async with semaphore:
                    return await process_single_pdf(
                        s3_client,
                        pdf_key,
                        settings.SOURCE_BUCKET,
                        settings.DEST_BUCKET,
                        settings.CROP_REGIONS
                    )
            
            # Process PDFs concurrently
            tasks = [process_with_semaphore(key) for key in pdf_keys]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes and errors
            success_count = 0
            error_count = 0
            valid_results = []
            
            for result in results:
                if isinstance(result, Exception):
                    error_count += 1
                    logger.error("Task failed with exception", error=str(result))
                elif result.status == ProcessingStatus.SUCCESS:
                    success_count += 1
                    valid_results.append(result)
                else:
                    error_count += 1
                    valid_results.append(result)
            
            # Create results DataFrame and save to S3
            if valid_results:
                df_data = [result.to_dict() for result in valid_results]
                df = pl.DataFrame(df_data)
                
                # Save results to S3
                results_key = f"results/batch_{batch_id}_results.parquet"
                parquet_data = df.write_parquet()
                
                await s3_client.put_object(
                    Bucket=settings.DEST_BUCKET,
                    Key=results_key,
                    Body=parquet_data,
                    ContentType="application/octet-stream"
                )
                
                logger.info("Saved batch results", 
                           batch_id=batch_id, results_key=results_key)
            
            # Invoke next batch if there are more PDFs
            if len(pdf_keys) == settings.BATCH_SIZE:
                last_key = pdf_keys[-1]
                await _invoke_next_batch(last_key, batch_id + 1)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            batch_result = BatchResult(
                batch_id=batch_id,
                processed=len(pdf_keys),
                success=success_count,
                errors=error_count,
                processing_time_ms=processing_time,
                status=ProcessingStatus.SUCCESS
            )
            
            logger.info("Completed batch processing", 
                       batch_id=batch_id, 
                       processed=len(pdf_keys),
                       success=success_count,
                       errors=error_count,
                       processing_time_ms=processing_time)
            
            return batch_result.to_dict()
            
    except Exception as e:
        processing_time = int((time.time() - start_time) * 1000)
        logger.error("Batch processing failed", 
                    batch_id=batch_id, error=str(e), 
                    processing_time_ms=processing_time)
        
        error_result = BatchResult(
            batch_id=batch_id,
            processed=0,
            success=0,
            errors=1,
            processing_time_ms=processing_time,
            status=ProcessingStatus.ERROR
        )
        
        return error_result.to_dict()


async def _invoke_next_batch(start_after: str, next_batch_id: int) -> None:
    """Invoke Lambda function for the next batch.
    
    Args:
        start_after: S3 key to start next batch from
        next_batch_id: ID for the next batch
    """
    settings = get_settings()
    
    if not settings.LAMBDA_NAME:
        logger.warning("Lambda function name not set, cannot invoke next batch")
        return
    
    try:
        lambda_client: LambdaClient = boto3.client('lambda')
        
        payload = {
            "start_after": start_after,
            "batch_id": next_batch_id
        }
        
        await lambda_client.invoke(
            FunctionName=settings.LAMBDA_NAME,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        
        logger.info("Invoked next batch", 
                   start_after=start_after, next_batch_id=next_batch_id)
        
    except Exception as e:
        logger.error("Failed to invoke next batch", 
                    start_after=start_after, next_batch_id=next_batch_id, 
                    error=str(e))


def lambda_handler(event: S3Event, context: Context) -> Dict[str, Any]:
    """AWS Lambda entry point."""
    try:
        start_after = event.get("start_after")
        batch_id = event.get("batch_id", 0)
        
        logger.info("Lambda invocation started", 
                   start_after=start_after, batch_id=batch_id)
        
        # Run the async batch processing
        result = asyncio.run(run_batch(start_after, batch_id))
        
        logger.info("Lambda invocation completed", result=result)
        return result
        
    except Exception as e:
        logger.error("Lambda handler failed", error=str(e))
        
        error_result = BatchResult(
            batch_id=event.get("batch_id", 0),
            processed=0,
            success=0,
            errors=1,
            processing_time_ms=0,
            status=ProcessingStatus.ERROR
        )
        
        return error_result.to_dict()

