# Build stage
FROM python:3.12-slim AS builder

WORKDIR /build

# Install dependencies
COPY pyproject.toml uv.lock ./
COPY bp_ecg_etl/ ./bp_ecg_etl/
RUN pip install --no-cache-dir uv && \
    uv pip install --no-cache --python $(which python) --target /deps .

# Runtime stage - minimal
FROM python:3.12-slim

WORKDIR /app

# Copy only dependencies and app code
COPY --from=builder /deps /usr/local/lib/python3.12/site-packages/
COPY bp_ecg_etl/ ./bp_ecg_etl/

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1

# Security: non-root user
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

# Entry point
CMD ["python", "-m", "bp_ecg_etl.main"]
