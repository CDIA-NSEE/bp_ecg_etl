# Multi-stage build for optimal image size
FROM python:3.12-slim AS builder

# Install UV for fast dependency installation
RUN pip install --no-cache-dir uv

WORKDIR /build

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies to a local directory
RUN uv pip install --no-cache --target /build/deps .

# Final stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy installed dependencies from builder
COPY --from=builder /build/deps /usr/local/lib/python3.12/site-packages/

# Copy application code
COPY bp_ecg_etl/ ./bp_ecg_etl/

# Set Python path
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import bp_ecg_etl; print('OK')" || exit 1

# Run as non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Entry point
CMD ["python", "-m", "bp_ecg_etl.main"]
