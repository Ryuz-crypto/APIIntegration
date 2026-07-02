FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar pyproject.toml primero para aprovechar el caché de Docker
COPY pyproject.toml ./

# Instalar dependencias con caché de pip y timeout aumentado
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade --retries 5 --timeout 60 pip \
    && pip install --no-cache-dir --retries 5 --timeout 60 .

# Copiar el código fuente después de instalar dependencias
COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
