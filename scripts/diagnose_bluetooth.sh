#!/usr/bin/env bash
# Diagnóstico rápido del estado Bluetooth del vLinker MC+ en Raspberry Pi.
# Uso:
#   sudo ./scripts/diagnose_bluetooth.sh [MAC]
#
# Si no se pasa MAC, se usa OBD_BT_MAC o el valor por defecto de este coche.

set -uo pipefail

OBD_BT_MAC="${1:-${OBD_BT_MAC:-04:25:E8:5B:01:EB}}"

echo "======================================"
echo "Diagnóstico Bluetooth OBD-II"
echo "MAC: $OBD_BT_MAC"
echo "======================================"
echo

echo "--- Adaptador Bluetooth del sistema ---"
hciconfig -a 2>/dev/null | head -n 10 || echo "hciconfig no disponible (prueba con 'hciconfig -a')"

echo
echo "--- Estado del servicio bluetoothd ---"
systemctl is-active bluetooth 2>/dev/null || echo "bluetoothd NO está activo"

echo
echo "--- Dispositivos emparejados ---"
bluetoothctl paired-devices 2>/dev/null || echo "(vacío o bluetoothctl no responde)"

echo
echo "--- Información del adaptador $OBD_BT_MAC ---"
bluetoothctl info "$OBD_BT_MAC" 2>/dev/null || echo "No hay info (¿no emparejado?)"

echo
echo "--- Servicios SDP (SPP) del adaptador ---"
if command -v sdptool >/dev/null 2>&1; then
    sdptool browse "$OBD_BT_MAC" 2>/dev/null | grep -E "(Service Name|Channel)" || echo "sdptool no encontró servicios SPP"
else
    echo "sdptool no disponible; instala bluez si quieres autodetección de canal."
fi

echo
echo "--- Dispositivos rfcomm ---"
rfcomm -a 2>/dev/null || echo "No hay bindings rfcomm activos"

if [[ -c /dev/rfcomm0 ]]; then
    echo
echo "--- /dev/rfcomm0 existe ---"
    ls -l /dev/rfcomm0 2>/dev/null
else
    echo
echo "--- /dev/rfcomm0 NO existe todavía ---"
fi

echo
echo "======================================"
echo "Si la información del dispositivo no muestra 'Paired: yes' y 'Trusted: yes',"
echo "empareja manualmente con PIN 1234:"
echo "  bluetoothctl agent NoInputNoOutput"
echo "  bluetoothctl pair $OBD_BT_MAC   # introducir 1234 si pide PIN"
echo "  bluetoothctl trust $OBD_BT_MAC"
echo "Si aparece 'vLinker MC-IOS' en lugar de 'vLinker MC-Android', pulsa el"
echo "botón del adaptador hasta ver el nombre Android (modo Bluetooth Classic SPP)."
