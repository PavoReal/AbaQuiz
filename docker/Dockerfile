# AbaQuiz Dockerfile
# Multi-stage build for optimized production image

# =============================================================================
# Stage 1: Builder - Install dependencies
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 2: Production - Minimal runtime image
# =============================================================================
FROM python:3.11-slim AS production

WORKDIR /app

# Create non-root user for security
RUN groupadd --gid 1000 abaquiz && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home abaquiz

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY src/ ./src/

# Create directories for data and config
RUN mkdir -p /app/data /app/config && \
    chown -R abaquiz:abaquiz /app

# Switch to non-root user
USER abaquiz

# Environment variables with defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_PATH=/app/data/abaquiz.db \
    LOG_LEVEL=INFO \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8070

# Expose web admin port
EXPOSE 8070

# Health check (checks if process is running)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python -m src.main" || exit 1

# Default command - run the bot
CMD ["python", "-m", "src.main"]

# Alternative commands:
# Web-only mode: CMD ["python", "-m", "src.main", "--web-only"]
