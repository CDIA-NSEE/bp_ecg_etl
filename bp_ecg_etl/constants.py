"""Constants for PDF anonymization."""

from typing import Final

# Processing constants
PADDING: Final[float] = 1.0
LINE_TOLERANCE: Final[float] = 1.0
PREVLINE_TOLERANCE: Final[float] = 10.0
DPI_PAGE2_RENDER: Final[int] = 150

# Text labels that should be REMOVED (anonymized)
LABELS_SAME_LINE: Final[list[str]] = [
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

# Text labels that should be PRESERVED (not anonymized)
KEEP_LABELS: Final[list[str]] = [
    "Sexo:",
    "Data:",
    "Hora:",
    "Data de Nascimento:",
    "Frequência cardíaca:",
    "Intervalo PR:",
    "Duração QRS:",
    "Intervalo QT/QTc:",
    "Eixo P-QRS-T:",
    "Interpretação:",
]

# CRM detection tokens
CRM_TOKENS: Final[list[str]] = ["CRM", "CRM:", "crm"]

# Coordinate-based redaction areas (relative coordinates 0-1)
PAGE1_REDACT_COORDS: Final[list[tuple[float, float, float, float]]] = [
    (0.35, 0.90, 0.65, 0.95),  # Footer signature/CRM area
]

PAGE2_REDACT_COORDS: Final[list[tuple[float, float, float, float]]] = [
    (0.02, 0.10, 0.12, 0.17),  # Top left (Name/RG)
    (0.13, 0.10, 0.18, 0.135),  # Top left (CPF)
    (0.40, 0.94, 0.98, 0.97),  # Footer (signature/CRM bar)
    (0.88, 0.85, 0.96, 0.92),  # Footer (right block)
]
