# =============================================================================
# Multi-Architecture Dockerfile for Investment Calculator
# Supports: linux/amd64, linux/arm64, linux/riscv64
#
# - amd64/arm64: Uses official python:3.11-slim (pre-built numpy wheels)
# - riscv64: Uses debian:trixie-slim + system Python, builds numpy
#   from source with OpenBLAS
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Architecture-specific base images
# ---------------------------------------------------------------------------

# --- riscv64 base: Debian Trixie (first stable release with riscv64 support) ---
FROM debian:trixie-slim AS base-riscv64

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Symlink python -> python3 so scripts work uniformly
RUN ln -sf /usr/bin/python3 /usr/bin/python

# --- amd64 base ---
FROM python:3.11-slim AS base-amd64

# --- arm64 base ---
FROM python:3.11-slim AS base-arm64

# ---------------------------------------------------------------------------
# Stage 2: Select the correct base using TARGETARCH (set by docker buildx)
# ---------------------------------------------------------------------------
ARG TARGETARCH
FROM base-${TARGETARCH} AS production

WORKDIR /app

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production

# ---------------------------------------------------------------------------
# Stage 3: Install build dependencies (needed for numpy on riscv64,
# also used on other arches if no wheel is available)
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Stage 4: Install Python dependencies
# ---------------------------------------------------------------------------
COPY requirements.txt .

# On riscv64, pip needs --break-system-packages since we use the system Python.
# We also allow building from source since no wheels exist for riscv64.
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "riscv64" ]; then \
        pip3 install --no-cache-dir --break-system-packages -r requirements.txt; \
    else \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# ---------------------------------------------------------------------------
# Stage 5: Remove build dependencies to reduce image size
# Keep runtime libraries (libopenblas, liblapack, libgfortran) for numpy
# ---------------------------------------------------------------------------
RUN apt-get update \
    && apt-mark manual libopenblas0 liblapack3 libgfortran5 2>/dev/null || true \
    && apt-get purge -y --auto-remove \
        build-essential \
        gfortran \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Stage 6: Copy application code and run
# ---------------------------------------------------------------------------
COPY . .

EXPOSE 80

CMD ["gunicorn", "--bind", "0.0.0.0:80", "--workers", "2", "app:app"]
