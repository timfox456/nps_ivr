# Production Dockerfile for NPS IVR
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy dependency files
COPY pyproject.toml ./
COPY requirements-base.txt ./

# Install Python dependencies using uv (SQLite version - no PostgreSQL)
RUN uv pip install --system -r requirements-base.txt

# Copy application code
COPY app/ ./app/

# Create directory for SQLite database
RUN mkdir -p /data

# Set environment for container mode
ENV CONTAINER=true \
    LOG_TO_FILE=false \
    LOG_FORMAT=json \
    ASYNC_LOGGING=true

# Expose application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
