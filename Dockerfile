# Build stage
FROM python:3.12-alpine AS builder

WORKDIR /build

# Install build dependencies for PyMuPDF and other packages
RUN apk add --no-cache \
    gcc \
    musl-dev \
    mupdf-dev \
    freetype-dev \
    harfbuzz-dev \
    openjpeg-dev \
    jbig2dec-dev \
    jpeg-dev \
    zlib-dev

# Install uv and dependencies
COPY pyproject.toml uv.lock ./
COPY bp_ecg_etl/ ./bp_ecg_etl/
RUN pip install --no-cache-dir uv && \
    uv pip install --no-cache --python $(which python) --target /deps . && \
    # Remove unnecessary files from deps
    find /deps -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /deps -type d -name "*.dist-info" -exec rm -rf {}/RECORD {} + 2>/dev/null || true && \
    find /deps -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /deps -name "*.pyc" -delete && \
    find /deps -name "*.pyo" -delete

# Runtime stage - minimal
FROM python:3.12-alpine

WORKDIR /app

# Install only runtime dependencies (no build tools)
RUN apk add --no-cache \
    libstdc++ \
    mupdf-dev \
    freetype \
    harfbuzz \
    openjpeg \
    jbig2dec \
    jpeg \
    zlib && \
    # Create non-root user
    adduser -D -u 1000 app && \
    chown -R app:app /app

# Copy only dependencies and app code
COPY --from=builder /deps /usr/local/lib/python3.12/site-packages/
COPY --chown=app:app bp_ecg_etl/ ./bp_ecg_etl/

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1

# Security: non-root user
USER app

# Entry point
CMD ["python", "-m", "bp_ecg_etl.main"]
