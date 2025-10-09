"""
Lambda handler para eventos S3 individuais.
"""

import asyncio
import json
import structlog

from .batch_processor import execute_batch
from .config import INPUT_BUCKET

logger = structlog.get_logger(__name__)


async def async_s3_handler(event: dict, context) -> dict:
    """
    Handler para eventos S3.
    
    Event: S3 event notification format
    {
        "Records": [{
            "s3": {
                "bucket": {"name": "..."},
                "object": {"key": "..."}
            }
        }]
    }
    """
    try:
        # Extrair keys dos Records S3
        keys = []
        records = event.get("Records", [])
        
        for record in records:
            s3_info = record.get("s3", {})
            object_info = s3_info.get("object", {})
            key = object_info.get("key")
            if key:
                keys.append(key)
        
        if not keys:
            logger.warning("No keys found in S3 event", event=event)
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No keys found in event"})
            }
        
        logger.info("Processing S3 event", keys_count=len(keys), keys=keys)
        
        # Processar arquivos
        summary = await execute_batch(
            keys=keys,
            bucket=INPUT_BUCKET,
            max_workers=15,
            function_name=None,
            context=context,
        )
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Processed {len(keys)} file(s)",
                "summary": summary
            })
        }
        
    except Exception as e:
        logger.error("Error processing S3 event", error=str(e), event=event)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def lambda_handler(event: dict, context) -> dict:
    """Entry point for S3 events."""
    return asyncio.run(async_s3_handler(event, context))
