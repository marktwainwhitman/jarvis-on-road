#!/usr/bin/env bash
# Mantiene /dev/rfcomm0 vinculado al vLinker MC+ (modo Android Classic SPP).
#
# Se ejecuta como servicio systemd (scripts/obd_rfcomm_keepalive.service). Cuando
# el coche se apaga y el enlace Bluetooth se cae, rfcomm connect termina y
# systemd reinicia el servicio automaticamente.
#
# Variables de entorno (pueden venir de .env o del fichero .service):
#   OBD_BT_MAC        MAC del adaptador (default: 04:25:E8:5B:01:EB)
#   OBD_BT_CHANNEL    Canal RFCOMM fijo (autodetectado si vacio)
#   OBD_RETRIES       Intentos de espera a bluetoothd (default: 10)

set -uo pipefail

OBD_BT_MAC="${OBD_BT_MAC:-04:25:E8:5B:01:EB}"
OBD_BT_CHANNEL="${OBD_BT_CHANNEL:-}"
OBD_RETRIES="${OBD_RETRIES:-10}"
RFOMM_NR="${OBD_RFCOMM_NR:-0}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

if ! command -v rfcomm >/dev/null 2>&1; then
    log "ERROR: rfcomm no encontrado. Instala bluez:"
    log "  sudo apt update && sudo apt install -y bluez"
    exit 1
fi

# -----------------------------------------------------------------------------
# Espera a que bluetoothd esté activo
# -----------------------------------------------------------------------------
for i in $(seq 1 "$OBD_RETRIES"); do
    if systemctl is-active --quiet bluetooth 2>/dev/null; then
        log "bluetoothd activo."
        break
    fi
    log "Esperando a bluetoothd... ($i/$OBD_RETRIES)"
    sleep 1
done

if ! systemctl is-active --quiet bluetooth 2>/dev/null; then
    log "ERROR: bluetoothd no está activo."
    exit 1
fi

# -----------------------------------------------------------------------------
# Detecta canal SPP
# -----------------------------------------------------------------------------
find_spp_channel() {
    local mac="$1"
    local channel=""

    if command -v sdptool >/dev/null 2>&1; then
        channel=$(sdptool browse "$mac" 2>/dev/null \
            | awk '
                /Service Name: .*Serial Port/ || /Service Name: .*SPP/ || /Service Name: .*vLinker/ {p=1}
                p && /Channel:/ {print $2; exit}
            ' || true)
    fi

    if [[ -z "$channel" ]] || ! [[ "$channel" =~ ^[0-9]+$ ]]; then
        channel=1
    fi
    echo "$channel"
}

if [[ -n "$OBD_BT_CHANNEL" ]]; then
    CHANNEL="$OBD_BT_CHANNEL"
    log "Usando canal RFCOMM forzado: $CHANNEL"
else
    CHANNEL=$(find_spp_channel "$OBD_BT_MAC")
    log "Canal RFCOMM detectado: $CHANNEL"
fi

# -----------------------------------------------------------------------------
# Bucle de reconexion
# -----------------------------------------------------------------------------
while true; do
    # Si ya existe el dispositivo, puede ser de un intento anterior caido;
    # lo liberamos para evitar conflictos.
    if [[ -e "/dev/rfcomm$RFOMM_NR" ]]; then
        rfcomm release "$RFOMM_NR" >/dev/null 2>&1 || true
        sleep 1
    fi

    log "Conectando $OBD_BT_MAC -> /dev/rfcomm$RFOMM_NR (canal $CHANNEL)..."
    rfcomm connect "$RFOMM_NR" "$OBD_BT_MAC" "$CHANNEL"

    # Si rfcomm connect termino, el enlace se cayó.
    log "Enlace rfcomm caido. Reintentando en 5 segundos..."
    sleep 5
done
