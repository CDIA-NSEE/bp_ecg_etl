# Build stage - Install dependencies using UV
FROM ghcr.io/astral-sh/uv:0.5.11-python3.12-bookworm-slim AS builder

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

# Use copy mode for better Docker layer caching
ENV UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first (separate layer for better caching)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application
COPY . /app

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Runtime stage - minimal production image
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --from=builder /app/bp_ecg_etl /app/bp_ecg_etl

# Create non-root user
RUN useradd -m -u 1000 app && \
    chown -R app:app /app

# Environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Security: run as non-root
USER app

# Entry point
CMD ["python", "-m", "bp_ecg_etl"]
