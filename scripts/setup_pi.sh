#!/usr/bin/env bash
# Prepara una Raspberry Pi para Jarvis On Road.
# Instala Docker, Docker Compose y activa Bluetooth.
# Ejecutar en la Raspberry Pi:
#   sudo bash scripts/setup_pi.sh

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Este script debe ejecutarse como root. Usa: sudo $0"
    exit 1
fi

echo "Actualizando paquetes..."
apt-get update
apt-get upgrade -y

echo "Instalando Docker..."
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
else
    echo "Docker ya está instalado."
fi

echo "Añadiendo usuario actual al grupo docker..."
usermod -aG docker "${SUDO_USER:-$USER}" || true

echo "Activando arranque automático de Docker..."
systemctl enable docker

echo "Activando Bluetooth..."
if command -v bluetoothctl >/dev/null 2>&1; then
    systemctl enable bluetooth
    systemctl start bluetooth
else
    apt-get install -y bluetooth bluez
    systemctl enable bluetooth
    systemctl start bluetooth
fi

echo ""
echo "Preparación completa."
echo "Reinicia la Raspberry Pi si es la primera vez que instalas Docker."
echo "Después, ejecuta:"
echo "  sudo bash scripts/setup_wifi_ap.sh"
echo "  docker compose up --build"
