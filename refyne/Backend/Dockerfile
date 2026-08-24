# ── Stage 1: Build dependencies ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime image ──────────────────────────────────────────────────
FROM python:3.12-slim AS production

# Install runtime-only system deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd -r refyne && useradd -r -g refyne -d /app -s /sbin/nologin refyne

WORKDIR /app

# Copy application code
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY evaluation/ evaluation/

# Create data directories and set ownership
RUN mkdir -p /app/data/chroma /app/data/documents /app/data/artifacts /app/data/objects && \
    chown -R refyne:refyne /app

USER refyne

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# ── Stage 3: Development (hot reload) ───────────────────────────────────────
FROM production AS development

USER root

RUN pip install --no-cache-dir ruff pytest pytest-asyncio httpx

RUN chown -R refyne:refyne /app

USER refyne

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
