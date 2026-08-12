#!/usr/bin/env bash
# Empareja y confia el vLinker MC+ (modo Android Classic SPP) UNA SOLA VEZ.
#
# Ejecutar esto ANTES de dejar la Raspberry sin teclado en el coche. Despues
# del emparejamiento, BlueZ recordara el dispositivo y los scripts de bind
# podran reconectar automaticamente.
#
# El adaptador debe estar conectado al coche (contacto puesto) y mostrar el
# nombre "vLinker MC-Android" (no "vLinker MC-IOS"; si ves iOS, pulsa el boton
# negro del adaptador hasta cambiar).
#
# Variables de entorno:
#   OBD_BT_MAC     MAC del adaptador (default: 04:25:E8:5B:01:EB)
#   OBD_BT_PIN     PIN de emparejamiento (default: 1234)

set -uo pipefail

OBD_BT_MAC="${OBD_BT_MAC:-04:25:E8:5B:01:EB}"
OBD_BT_PIN="${OBD_BT_PIN:-1234}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

if ! command -v bluetoothctl >/dev/null 2>&1; then
    log "ERROR: bluetoothctl no encontrado. Instala bluez:"
    log "  sudo apt update && sudo apt install -y bluez"
    exit 1
fi

if ! command -v expect >/dev/null 2>&1; then
    log "INFO: expect no encontrado; intentando instalar..."
    sudo apt-get update >/dev/null 2>&1 || true
    sudo apt-get install -y --no-install-recommends expect >/dev/null 2>&1 || true
fi

if ! command -v expect >/dev/null 2>&1; then
    log "ERROR: expect no se pudo instalar. Empareja manualmente con:"
    log "  bluetoothctl"
    log "  agent NoInputNoOutput"
    log "  pair $OBD_BT_MAC       # PIN $OBD_BT_PIN si lo pide"
    log "  trust $OBD_BT_MAC"
    exit 1
fi

log "Buscando $OBD_BT_MAC..."
log "Asegurate de que el adaptador muestra el nombre 'vLinker MC-Android'."

# Limpia emparejamiento previo para evitar estados rotos.
bluetoothctl remove "$OBD_BT_MAC" >/dev/null 2>&1 || true
sleep 1

expect -c "
set timeout 30
spawn bluetoothctl
expect \"#\"
send -- \"power on\r\"
expect \"#\"
send -- \"agent NoInputNoOutput\r\"
expect \"#\"
send -- \"default-agent\r\"
expect \"#\"
send -- \"scan on\r\"
expect \"#\"
send -- \"pair $OBD_BT_MAC\r\"
expect {
    \"PIN code\" { send -- \"$OBD_BT_PIN\r\"; exp_continue }
    \"Enter passkey\" { send -- \"$OBD_BT_PIN\r\"; exp_continue }
    \"Pairing successful\" { }
    \"Already paired\" { }
    \"Failed to pair\" { exit 1 }
    timeout { exit 1 }
}
expect \"#\"
send -- \"trust $OBD_BT_MAC\r\"
expect \"#\"
send -- \"quit\r\"
expect eof
"

if [[ $? -ne 0 ]]; then
    log "ERROR: no se pudo emparejar $OBD_BT_MAC."
    log "  - Verifica que el adaptador muestra 'vLinker MC-Android' (no iOS)."
    log "  - Intenta pulsar el boton del adaptador y repetir."
    exit 1
fi

log "Emparejamiento OK. Verificando estado:"
bluetoothctl info "$OBD_BT_MAC" | grep -E "(Name|Paired|Trusted|Connected)" || true

log "Hecho. Ahora ya puedes ejecutar scripts/obd_rfcomm_bind.sh o habilitar"
log "los servicios systemd para reconexion automatica."
