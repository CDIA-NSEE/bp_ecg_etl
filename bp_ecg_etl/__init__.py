"""BP-ECG ETL - Processamento paralelo simplificado de PDFs de ECG.

Processa lotes de PDFs com:
- Anonimização de dados sensíveis (página 1)
- Extração de ECG como PNG (página 2, 300 DPI)
- Processamento paralelo com asyncio (15 workers)
- Step Functions para escala (500 Lambdas simultâneas)
"""

from . import batch_processor
from . import config
from . import ecg_extractor
from . import logging_config
from . import pdf_anonymizer
from . import pdf_processor
from . import s3_utils
from .lambda_handler import lambda_handler

__version__ = "3.0.0"

__all__ = [
    "batch_processor",
    "config",
    "ecg_extractor",
    "lambda_handler",
    "logging_config",
    "pdf_anonymizer",
    "pdf_processor",
    "s3_utils",
]
