"""
Lambda handler simplificado para processar lotes de PDFs.

Recebe um lote de arquivos e processa cada um.
"""

import asyncio
import json
import structlog

from .batch_processor import execute_batch
from .config import INPUT_BUCKET

logger = structlog.get_logger(__name__)


async def async_handler(event: dict, context) -> dict:
    """
    Handler assíncrono para processar lote de PDFs.

    Event:
    {
        "keys": ["file1.pdf", "file2.pdf", ...]
    }
    """
    logger.info("Lambda invocada", keys_count=len(event.get("keys", [])))

    try:
        keys = event.get("keys", [])
        
        if not keys:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No keys provided"})
            }

        # Processar lote
        summary = await execute_batch(
            keys=keys,
            bucket=INPUT_BUCKET,
            max_workers=15,
            function_name=None,
            context=context,
        )

        return {
            "statusCode": 200,
            "body": json.dumps(summary, indent=2)
        }

    except Exception as e:
        logger.error("Erro no processamento", error=str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def lambda_handler(event: dict, context) -> dict:
    """Entry point AWS Lambda."""
    return asyncio.run(async_handler(event, context))
