#!/usr/bin/env bash
# Vincula el adaptador OBD-II Bluetooth vLinker MC+ (modo Android Classic SPP)
# al puerto serie /dev/rfcomm0.
#
# IMPORTANTE: el vLinker MC+ presenta dos interfaces Bluetooth:
#   - "vLinker MC-Android" -> Bluetooth Classic SPP (la que usa este script).
#   - "vLinker MC-IOS"     -> Bluetooth LE (NO funciona con rfcomm).
# En la Raspberry debes emparejar la interfaz Android. Si ves la versión iOS,
# pulsa el botón del adaptador hasta que aparezca "vLinker MC-Android".
#
# Variables de entorno:
#   OBD_BT_MAC        MAC del adaptador (obligatorio si OBD_MOCK=false)
#   OBD_MOCK          "true" para omitir todo
#   OBD_BT_PIN        PIN de emparejamiento (default: 1234)
#   OBD_BT_CHANNEL    Canal RFCOMM fijo (si no se indica se autodetecta)
#   OBD_RETRIES       Intentos de espera a bluetoothd (default: 10)
#   OBD_BIND_LOG      Fichero de log (default: /var/log/jarvis-obd-bind.log)

set -euo pipefail

OBD_BT_MAC="${OBD_BT_MAC:-04:25:E8:5B:01:EB}"
OBD_MOCK="${OBD_MOCK:-false}"
OBD_BT_PIN="${OBD_BT_PIN:-1234}"
OBD_BT_CHANNEL="${OBD_BT_CHANNEL:-}"
OBD_RETRIES="${OBD_RETRIES:-10}"
OBD_BIND_LOG="${OBD_BIND_LOG:-/var/log/jarvis-obd-bind.log}"
RFOMM_NR="${OBD_RFCOMM_NR:-0}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$OBD_BIND_LOG" >&2
}

mkdir -p "$(dirname "$OBD_BIND_LOG")"

if [[ "$OBD_MOCK" == "true" ]] || [[ -z "$OBD_BT_MAC" ]]; then
    log "OBD en modo mock o sin MAC configurada; se omite rfcomm bind."
    exit 0
fi

log "=== Inicio binding OBD-II Bluetooth ==="
log "MAC: $OBD_BT_MAC"
log "PIN: $OBD_BT_PIN"

# -----------------------------------------------------------------------------
# Asegura herramientas BlueZ
# -----------------------------------------------------------------------------
if ! command -v rfcomm >/dev/null 2>&1 || ! command -v bluetoothctl >/dev/null 2>&1; then
    log "rfcomm/bluetoothctl no están disponibles; intentando instalar bluez..."
    apt-get update >/dev/null 2>&1 || true
    apt-get install -y --no-install-recommends bluez >/dev/null 2>&1 || true
fi

if ! command -v expect >/dev/null 2>&1; then
    log "expect no está disponible; intentando instalar..."
    apt-get update >/dev/null 2>&1 || true
    apt-get install -y --no-install-recommends expect >/dev/null 2>&1 || true
fi

if ! command -v rfcomm >/dev/null 2>&1; then
    log "ERROR: rfcomm sigue sin estar disponible tras intentar instalar bluez."
    exit 1
fi

# Carga el módulo rfcomm si no está cargado.
modprobe rfcomm 2>/dev/null || true

# -----------------------------------------------------------------------------
# Espera a que bluetoothd esté activo
# -----------------------------------------------------------------------------
wait_bluetooth() {
    for i in $(seq 1 "$OBD_RETRIES"); do
        if systemctl is-active --quiet bluetooth 2>/dev/null; then
            log "bluetoothd activo."
            return 0
        fi
        log "Esperando a bluetoothd... ($i/$OBD_RETRIES)"
        sleep 1
    done
    log "ERROR: bluetoothd no está activo tras $OBD_RETRIES intentos."
    return 1
}

wait_bluetooth || exit 1

# -----------------------------------------------------------------------------
# Información actual del dispositivo
# -----------------------------------------------------------------------------
log "Estado actual del dispositivo:"
bluetoothctl info "$OBD_BT_MAC" 2>/dev/null | sed 's/^/  /' || true

# -----------------------------------------------------------------------------
# Emparejamiento/confianza con PIN
# -----------------------------------------------------------------------------
_is_paired() {
    bluetoothctl info "$OBD_BT_MAC" 2>/dev/null | grep -qi "Paired: yes"
}

_is_trusted() {
    bluetoothctl info "$OBD_BT_MAC" 2>/dev/null | grep -qi "Trusted: yes"
}

_is_connected() {
    bluetoothctl info "$OBD_BT_MAC" 2>/dev/null | grep -qi "Connected: yes"
}

pair_and_trust() {
    local mac="$1"
    log "Emparejando $mac con PIN $OBD_BT_PIN..."

    if command -v expect >/dev/null 2>&1; then
        expect -c "
            set timeout 20
            spawn bluetoothctl
            expect \"#\"
            send -- \"agent NoInputNoOutput\r\"
            expect \"#\"
            send -- \"default-agent\r\"
            expect \"#\"
            send -- \"remove $mac\r\"
            expect \"#\"
            send -- \"pair $mac\r\"
            expect {
                \"PIN code\" { send -- \"$OBD_BT_PIN\r\"; exp_continue }
                \"Enter passkey\" { send -- \"$OBD_BT_PIN\r\"; exp_continue }
                \"Pairing successful\" { }
                \"Failed to pair\" { exit 1 }
                \"Already paired\" { }
                timeout { exit 1 }
            }
            expect \"#\"
            send -- \"trust $mac\r\"
            expect \"#\"
            send -- \"quit\r\"
            expect eof
        " 2>&1 | sed 's/^/  expect: /' | tee -a "$OBD_BIND_LOG" >&2
    else
        log "AVISO: expect no está disponible; emparejamiento automático puede fallar."
        log "      Empareja manualmente con: bluetoothctl -> agent on -> pair $mac -> PIN $OBD_BT_PIN -> trust $mac"
        bluetoothctl <<EOF
agent NoInputNoOutput
default-agent
pair $mac
trust $mac
quit
EOF
    fi
}

if _is_paired && _is_trusted; then
    log "$OBD_BT_MAC ya está emparejado y confiado."
else
    pair_and_trust "$OBD_BT_MAC" || {
        log "ERROR: no se pudo emparejar $OBD_BT_MAC."
        log "  Asegúrate de que el coche tiene contacto/encendido y el adaptador"
        log "  muestra el nombre 'vLinker MC-Android' (no vLinker MC-IOS)."
        log "  Puedes emparejar manualmente con PIN $OBD_BT_PIN."
        exit 1
    }
fi

# Asegura confianza tras el emparejamiento.
bluetoothctl trust "$OBD_BT_MAC" >/dev/null 2>&1 || true

# -----------------------------------------------------------------------------
# Conecta el perfil serial (SPP). En algunos adaptadores acelera la
# creación de /dev/rfcomm0 y evita que rfcomm bind falle.
# -----------------------------------------------------------------------------
if ! _is_connected; then
    log "Intentando conectar perfil serial..."
    bluetoothctl connect "$OBD_BT_MAC" >/dev/null 2>&1 || true
    sleep 1
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
# Libera /dev/rfcommN si ya existe
# -----------------------------------------------------------------------------
release_rfcomm() {
    if [[ -e "/dev/rfcomm$RFOMM_NR" ]]; then
        log "Liberando /dev/rfcomm$RFOMM_NR previo..."
        rfcomm release "$RFOMM_NR" >/dev/null 2>&1 || true
        sleep 0.5
    fi
}

release_rfcomm

# -----------------------------------------------------------------------------
# Vincula
# -----------------------------------------------------------------------------
log "Vinculando $OBD_BT_MAC -> /dev/rfcomm$RFOMM_NR (canal $CHANNEL)..."
if rfcomm bind "$RFOMM_NR" "$OBD_BT_MAC" "$CHANNEL"; then
    log "rfcomm bind OK. Esperando a que aparezca /dev/rfcomm$RFOMM_NR..."
    for i in $(seq 1 10); do
        if [[ -c "/dev/rfcomm$RFOMM_NR" ]]; then
            log "/dev/rfcomm$RFOMM_NR disponible."
            break
        fi
        sleep 0.2
    done
else
    log "ERROR: rfcomm bind falló."
    log "  Intentando fallback rfcomm connect (bloqueante durante 10s)..."
    timeout 10 rfcomm connect "$RFOMM_NR" "$OBD_BT_MAC" "$CHANNEL" >/dev/null 2>&1 || true
fi

if [[ -c "/dev/rfcomm$RFOMM_NR" ]]; then
    log "Binding OBD-II Bluetooth OK: /dev/rfcomm$RFOMM_NR"
    exit 0
fi

log "ERROR: /dev/rfcomm$RFOMM_NR no está disponible tras intentar bind/connect."
log "  Posibles causas:"
log "    - El adaptador está en modo BLE (vLinker MC-IOS). Usa 'vLinker MC-Android'."
log "    - El coche no tiene contacto puesto; la ECU no responde."
log "    - Canal RFCOMM distinto. Prueba OBD_BT_CHANNEL=1 u OBD_BT_CHANNEL=2."
log "    - Emparejamiento perdido. Empareja manualmente con PIN $OBD_BT_PIN."
exit 1
