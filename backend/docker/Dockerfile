# --- Builder -----------------------------------------------------------------
# Multi-stage so the final image doesn't carry build tools / sources.

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# System packages required to build wheels (psycopg/pgvector/etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

# Install into a dedicated prefix we'll copy into the runtime image.
RUN pip install --upgrade pip \
    && pip install --prefix=/install ".[]"

COPY app ./app

# --- Runtime -----------------------------------------------------------------

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PYTHONPATH=/app

# Runtime libs only — no compilers in the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root for safety.
RUN useradd --create-home --shell /bin/bash gift && mkdir /app && chown gift:gift /app

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=gift:gift app /app/app
COPY --chown=gift:gift alembic.ini /app/alembic.ini

USER gift

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
