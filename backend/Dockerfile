FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────────────────
# gcc / g++  : compile C extensions (psycopg2-binary, tokenizers, etc.)
# libpq-dev  : PostgreSQL client headers required by psycopg2
# curl       : healthcheck helper
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python environment ────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Install dependencies (separate layer for Docker cache) ────────────────────
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copy source code ──────────────────────────────────────────────────────────
# In development the ./backend directory is volume-mounted over /app,
# so this COPY is mainly useful for production builds.
COPY . .

# ── Runtime directories ───────────────────────────────────────────────────────
RUN mkdir -p uploads data/chroma logs

EXPOSE 8000

# Default command — respects the PORT environment variable for cloud platforms like Render
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
