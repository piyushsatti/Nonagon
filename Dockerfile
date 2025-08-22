# ---------- Base image ----------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # <- Make src/ importable so `import app` works
    PYTHONPATH=/app/src

WORKDIR /app

# ---------- OS deps ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# ---------- Python deps ----------
# Cache-friendly: copy metadata first
COPY pyproject.toml ./
RUN python -m pip install --upgrade pip \
 && pip install "uvicorn[standard]" \
 && pip install .

# ---------- App code ----------
COPY src ./src

# ---------- Non-root ----------
RUN useradd -m appuser
USER appuser

# ---------- API port ----------
EXPOSE 8000

# ---------- Switch: API or Bot ----------
ARG SERVICE=api
ENV SERVICE=${SERVICE}

CMD ["/bin/sh", "-c", "if [ \"$SERVICE\" = \"api\" ]; then \
      uvicorn app.api.server:app --host 0.0.0.0 --port 8000; \
    else \
      python -m app.bot.main; \
    fi"]
