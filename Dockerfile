# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

# Instalamos toolchain de compilacion por si alguna dependencia nativa
# (uvloop, httptools, etc.) no tiene wheel para la arquitectura de la
# Raspberry Pi y debe compilarse desde fuente.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# --- Imagen final ---
FROM python:3.12-slim

WORKDIR /app

# Creamos usuario no-root para ejecutar la aplicacion.
RUN groupadd -r jarvis && useradd -r -g jarvis -d /app jarvis

# Copiamos el entorno virtual ya instalado y la aplicacion.
COPY --from=builder --chown=jarvis:jarvis /opt/venv /opt/venv
COPY --chown=jarvis:jarvis . .

USER jarvis

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["python", "src/main.py"]
