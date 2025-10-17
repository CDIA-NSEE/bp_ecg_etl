"""Configuration using environment variables."""

import os

# S3 Configuration
INPUT_BUCKET = os.getenv("INPUT_BUCKET", "raw-pdfs")
OUTPUT_BUCKET = os.getenv("OUTPUT_BUCKET", "anon-pdfs")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Concurrency Configuration (ECS/Lambda)
# OTIMIZADO PARA PERFORMANCE MÁXIMA COM PARALLELISM HÍBRIDO
# Recomendações por hardware:
#   - 8 CPUs + 16GB RAM: 16 processes + 200 async workers (OTIMIZADO)
#   - 4 CPUs + 8GB RAM: 8 processes + 100 async workers
#   - 16 CPUs + 32GB RAM: 32 processes + 400 async workers
#   - Lambda: Não recomendado (use ECS Fargate)
# Performance esperada: 16 processes @ 8 vCPUs = ~2-3 hours para 1.5M PDFs (3-4x mais rápido)
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "200"))  # Asyncio workers para I/O concorrente
QUEUE_SIZE = int(os.getenv("QUEUE_SIZE", "800"))  # Buffer size (4x MAX_WORKERS)
MAX_PROCESS_WORKERS = int(os.getenv("MAX_PROCESS_WORKERS", "16"))  # 0 = auto-detect (CPU count)
BATCH_UPLOAD_SIZE = int(os.getenv("BATCH_UPLOAD_SIZE", "50"))  # Upload em lotes

# Processing Configuration
# DPI for page 2 rasterization (higher = better quality, larger file)
# 220 = good (web), 300 = high (print), 450 = very high (medical archive)
# OTIMIZADO: 300 DPI oferece qualidade excelente com 4x menos processamento que 600
DPI_PAGE2_RENDER = int(os.getenv("DPI_PAGE2_RENDER", "450"))

# JPEG quality for page 2 rasterization (85-95 recommended for medical)
# PERFORMANCE: JPEG is 3-5x faster than PNG with minimal quality loss at 95
# 95 = excellent quality (recommended), 90 = high quality, 85 = good quality
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "95"))

# Compression Configuration
ZIP_COMPRESSION_LEVEL = int(os.getenv("ZIP_COMPRESSION_LEVEL", "3"))  # 1-9, 3 = fast + good ratio

# S3 Configuration
S3_MAX_POOL_CONNECTIONS = int(os.getenv("S3_MAX_POOL_CONNECTIONS", "50"))
S3_CONNECT_TIMEOUT = int(os.getenv("S3_CONNECT_TIMEOUT", "5"))
S3_READ_TIMEOUT = int(os.getenv("S3_READ_TIMEOUT", "30"))

# Anonymization Rules
LINE_TOLERANCE = float(os.getenv("LINE_TOLERANCE", "1.0"))
PREVLINE_TOLERANCE = float(os.getenv("PREVLINE_TOLERANCE", "10.0"))
PADDING = float(os.getenv("PADDING", "1.0"))

# Text Labels
# Labels que devem ter seus valores REMOVIDOS (anonimizados)
LABELS_SAME_LINE = [
    "Nome:",
    "CPF:",
    "RG:",
    "Reg. Clínico:",
    "Registro Clínico:",
    "Convênio:",
    "Convenio:",
    "Responsável:",
    "Responsavel:",
    "Solicitante:",
    "Médico Responsável:",
    "Medico Responsavel:",
    "Idade:",
    "CRM:",
    "Médico:",
]

# Labels que devem ter seus valores PRESERVADOS (não anonimizados)
KEEP_LABELS = [
    "Sexo:",
    "Data:",
    "Hora:",  # Labels reais do PDF
    "Data de Nascimento:",
    "Frequência cardíaca:",
    "Intervalo PR:",
    "Duração QRS:",
    "Intervalo QT/QTc:",
    "Eixo P-QRS-T:",
    "Interpretação:",
]

CRM_TOKENS = ["CRM", "CRM:", "crm"]

# Coordinate-based redaction areas (relative coordinates 0-1)
PAGE1_REDACT_COORDS = [
    (0.35, 0.87, 0.65, 0.98),  # Footer signature/CRM area
]

PAGE2_REDACT_COORDS = [
    (0.02, 0.10, 0.12, 0.17),   # Top left (Name/RG)
    (0.13, 0.10, 0.18, 0.135),  # Top left (CPF)
    (0.40, 0.94, 0.98, 0.97),   # Footer (signature/CRM bar)
    (0.88, 0.85, 0.96, 0.92),   # Footer (right block)
]
