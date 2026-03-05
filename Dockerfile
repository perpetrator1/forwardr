
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ libffi-dev libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# runtime stage
FROM python:3.11-slim

WORKDIR /app

# libmagic is needed at runtime by python-magic
RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 curl \
    && rm -rf /var/lib/apt/lists/*

# copy only the installed packages from the builder
COPY --from=builder /install /usr/local

# copy application code
COPY . .

RUN mkdir -p /app/logs /app/media

# default port
ENV PORT=8000

EXPOSE ${PORT}

# health-check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:${PORT}/health || exit 1

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
