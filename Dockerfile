# Dockerfile
# AEP backend – FastAPI + Uvicorn, production-ready on AWS App Runner

FROM python:3.11-slim AS base

# Prevent Python from buffering stdout/stderr (better logs)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # opentelemetry-proto <5.0 requires old-style .pb2 descriptors that break
    # under the protobuf C extension (upb) when protobuf>=5.x is installed.
    # Force pure-Python implementation so old .pb2 files work.
    # Remove once chromadb upgrades opentelemetry-exporter-otlp-proto-grpc to
    # a version whose opentelemetry-proto declares protobuf>=5 compatibility.
    PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

# Set workdir
WORKDIR /app

# Install system deps you might need (build wheels, git, ffmpeg for video processing, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# If your requirements file is elsewhere, adjust the path.
COPY requirements.txt ./requirements.txt

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of your backend code
# (Assumes backend/ is in repo root as in your screenshots)
COPY . .

# Create data directory for SQLite (if using local SQLite)
RUN mkdir -p /app/data

# Default port for AEP backend
ENV PORT=8787

# App Runner will send traffic to this port
EXPOSE 8787

# Health check (optional but nice if App Runner probes it)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8787/health/live || exit 1

# Start FastAPI via Uvicorn
# Adjust the module path if your main app is elsewhere
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8787"]