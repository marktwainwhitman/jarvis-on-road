#!/usr/bin/env bash
# Vincula el adaptador OBD-II Bluetooth al puerto serie /dev/rfcomm0.
# Se ejecuta en el host (Raspberry Pi) ANTES de levantar el contenedor.
# Variables de entorno:
#   OBD_BT_MAC      MAC del adaptador OBD-II (obligatorio si OBD_MOCK=false)
#   OBD_MOCK        si es "true", no hace nada
#   OBD_RETRIES     intentos de espera a bluetoothd (default: 10)

set -euo pipefail

OBD_BT_MAC="${OBD_BT_MAC:-}"
OBD_MOCK="${OBD_MOCK:-false}"
OBD_RETRIES="${OBD_RETRIES:-10}"

if [[ "$OBD_MOCK" == "true" ]] || [[ -z "$OBD_BT_MAC" ]]; then
    echo "OBD en modo mock o sin MAC configurada; se omite rfcomm bind."
    exit 0
fi

if ! command -v rfcomm >/dev/null 2>&1; then
    echo "rfcomm no esta instalado; intentando instalar bluez..."
    apt-get update >/dev/null 2>&1 || true
    apt-get install -y bluez >/dev/null 2>&1 || true
fi

# Espera a que bluetooth este activo.
for i in $(seq 1 "$OBD_RETRIES"); do
    if systemctl is-active --quiet bluetooth 2>/dev/null; then
        break
    fi
    echo "Esperando a bluetoothd... ($i/$OBD_RETRIES)"
    sleep 1
done

if [[ -e /dev/rfcomm0 ]]; then
    echo "/dev/rfcomm0 ya existe; no se vuelve a vincular."
    exit 0
fi

echo "Vinculando $OBD_BT_MAC a /dev/rfcomm0..."
if rfcomm bind 0 "$OBD_BT_MAC" 1; then
    echo "rfcomm0 vinculado correctamente."
else
    echo "ADVERTENCIA: no se pudo vincular $OBD_BT_MAC. El contenedor seguira" \
         "arrancando y el lector OBD reintentara la conexion por software."
fi
