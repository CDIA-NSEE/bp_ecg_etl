"""Simple configuration using environment variables."""

import os

# S3 Configuration
INPUT_BUCKET = os.getenv("INPUT_BUCKET", "test-input-bucket")
OUTPUT_BUCKET = os.getenv("OUTPUT_BUCKET", "test-output-bucket")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Processing Configuration
DPI_PAGE2_RENDER = int(os.getenv("DPI_PAGE2_RENDER", "220"))
IMAGE_REDACT_MODE = int(os.getenv("IMAGE_REDACT_MODE", "2"))  # 1 = PDF_REDACT_IMAGE_NONE

# Anonymization Rules
LINE_TOLERANCE = float(os.getenv("LINE_TOLERANCE", "1.0"))
PREVLINE_TOLERANCE = float(os.getenv("PREVLINE_TOLERANCE", "10.0"))
PADDING = float(os.getenv("PADDING", "1.0"))

# Text Labels
# Labels que devem ter seus valores REMOVIDOS (anonimizados)
LABELS_SAME_LINE = [
    "Nome:", "CPF:", "RG:",
    "Reg. Clínico:", "Registro Clínico:",
    "Convênio:", "Convenio:",
    "Responsável:", "Responsavel:",
    "Solicitante:",
    "Médico Responsável:", "Medico Responsavel:", "Idade:",
    "CRM:", "Médico:"
]

# Labels que devem ter seus valores PRESERVADOS (não anonimizados)
KEEP_LABELS = [
    "Sexo:", "Data:", "Hora:",  # Labels reais do PDF
    "Data de Nascimento:", 
    "Frequência cardíaca:", "Intervalo PR:", "Duração QRS:",
    "Intervalo QT/QTc:", "Eixo P-QRS-T:", "Interpretação:"
]

CRM_TOKENS = ["CRM", "CRM:", "crm"]

# Coordinate-based redaction areas (relative coordinates 0-1)
PAGE1_REDACT_COORDS = [
    (0.35, 0.90, 0.65, 0.95),  # Footer signature/CRM area
    (50, 50, 200, 80),   # Example coordinates - adjust as needed
    (300, 100, 500, 130)
]

PAGE2_REDACT_COORDS = [
    (0.02, 0.10, 0.12, 0.17),   # Top left (Name/RG...)
    (0.13, 0.10, 0.18, 0.135),  # Top left (CPF...)
    (0.40, 0.94, 0.98, 0.97),   # Footer (signature/CRM bar)
    (0.88, 0.85, 0.96, 0.92),   # Footer (right block)
    (100, 200, 400, 250),  # Example coordinates - adjust as needed
    (50, 300, 300, 350)
]

# Image processing
IMAGE_REDACT_MODE = "RGB"
