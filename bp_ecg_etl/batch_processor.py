"""Processador de lotes de PDFs com redação vetorial."""

import asyncio
import time
from typing import Any

import structlog

from .config import DPI_PAGE2_RENDER, OUTPUT_BUCKET
from .pdf_processor import process_complete_pdf
from .s3_utils import download_pdf, generate_output_key, upload_pdf

logger = structlog.get_logger(__name__)


async def process_single_pdf(bucket: str, key: str, dpi: int = DPI_PAGE2_RENDER) -> dict[str, Any]:
    """Processa um PDF: download, anonimização vetorial, upload."""
    start = time.time()

    try:
        # Download
        pdf_bytes = await download_pdf(bucket, key)

        # Processar (CPU-bound, roda em thread separada)
        processed_bytes = await asyncio.to_thread(process_complete_pdf, pdf_bytes, dpi)

        # Upload
        output_key = generate_output_key(key)
        await upload_pdf(
            OUTPUT_BUCKET,
            output_key,
            processed_bytes,
            metadata={
                "original-key": key,
                "original-bucket": bucket,
                "anonymized": "true",
                "method": "vectorial",
            },
        )

        elapsed = time.time() - start
        logger.info("PDF processado (vectorial)", key=key, time=round(elapsed, 2))

        return {"status": "success", "key": key, "time": elapsed}

    except Exception as e:
        logger.error("Erro processando PDF", key=key, error=str(e))
        return {"status": "error", "key": key, "error": str(e)}


async def execute_batch(keys: list[str], bucket: str, max_workers: int = 15, **kwargs) -> dict[str, Any]:
    """Executa processamento de lote com workers assíncronos."""
    start_time = time.time()
    results = []
    queue = asyncio.Queue()

    # Adiciona keys na fila
    for key in keys:
        await queue.put(key)

    # Worker
    async def worker():
        while True:
            try:
                key = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                break

            result = await process_single_pdf(bucket, key)
            results.append(result)
            queue.task_done()

    # Inicia workers
    workers = [asyncio.create_task(worker()) for _ in range(max_workers)]

    # Aguarda workers
    await queue.join()

    # Cancela workers
    for w in workers:
        w.cancel()

    # Sumário
    successful = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "error")

    return {
        "status": "completed",
        "processed": len(results),
        "successful": successful,
        "failed": failed,
        "time": round(time.time() - start_time, 2),
    }
