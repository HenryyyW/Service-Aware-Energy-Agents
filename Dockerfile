# Production Dockerfile for Service-Aware Energy Agents API
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml README.md ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[api]"

# Copy application code
COPY src/ ./src/
COPY configs/ ./configs/
COPY experiments/ ./experiments/
COPY tests/ ./tests/
COPY backend/ ./backend/

# Bake the CityLearn dataset into the appuser cache so the adapter's
# fallback chain (~/.cache/citylearn/v3.0.2/datasets/<name>) resolves without
# a network download (containers fail fast on missing data by design).
COPY --chown=appuser:appuser experiments/reference/citylearn_challenge_2020_climate_zone_1 /home/appuser/.cache/citylearn/v3.0.2/datasets/citylearn_challenge_2020_climate_zone_1

# Also bake the with_evs dataset (no curated fixture; download at build time)
# Run as root so it lands in /root/.cache AND copy to /app/citylearn_datasets for the adapter's fallback chain.
RUN python3 -c "
from citylearn.data import DataSet
dataset = DataSet()
schema = dataset.get_schema('citylearn_challenge_2022_phase_all_plus_evs')
import shutil, os
src = schema['root_directory']
dst = '/app/citylearn_datasets/citylearn_challenge_2022_phase_all_plus_evs'
if os.path.exists(src):
    shutil.copytree(src, dst, dirs_exist_ok=True)
    print(f'Copied with_evs dataset from {src} to {dst}')
else:
    print(f'WARNING: with_evs dataset not found at {src}')
"

# Create necessary directories (including schemas for per-run CityLearn files)
RUN mkdir -p /app/logs /app/data /app/results /app/schemas /app/citylearn_datasets && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with gunicorn
CMD ["gunicorn", "backend.app.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]