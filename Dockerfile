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

# Copiamos el entorno virtual ya instalado y la aplicacion.
COPY --from=builder /opt/venv /opt/venv
COPY . .

# Se ejecuta como root (el contenedor ya corre con privileged: true en
# docker-compose.yml para acceder a BLE/serie). docker-compose monta el
# repo del host como bind mount (".:/app"), asi que un usuario no-root aqui
# no tendria permisos de escritura sobre "data/" ni sobre /dev/rfcomm0 en el
# host salvo que sus UID/GID coincidieran exactamente con los del host, lo
# que complicaria el arranque "sin tocar nada" tras un git pull.
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["python", "src/main.py"]
