FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Usar espejo de PyPI de Tsinghua (rápido y confiable)
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_DEFAULT_TIMEOUT=120

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar metadatos y código requeridos para construir el paquete
COPY pyproject.toml ./
COPY app ./app

# Instalar dependencias con caché de pip y timeout aumentado
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --retries 5 --timeout 120 .

COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
