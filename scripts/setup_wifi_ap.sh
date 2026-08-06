#!/usr/bin/env bash
# Configura la Raspberry Pi como punto de acceso WiFi para Jarvis On Road.
# Pensado para Raspberry Pi OS Bookworm o posterior (usa NetworkManager).
# Ejecutar en la Raspberry Pi:
#   sudo bash scripts/setup_wifi_ap.sh

set -euo pipefail

SSID="${JARVIS_AP_SSID:-JarvisOnRoad}"
PASSWORD="${JARVIS_AP_PASSWORD:-Jarvis1234}"
IFACE="${JARVIS_AP_IFACE:-wlan0}"
IP_RANGE="${JARVIS_AP_IP:-192.168.4.1/24}"
CONN_NAME="${JARVIS_AP_CONN:-JarvisOnRoad-AP}"

if [[ $EUID -ne 0 ]]; then
    echo "Este script debe ejecutarse como root. Usa: sudo $0"
    exit 1
fi

if ! command -v nmcli >/dev/null 2>&1; then
    echo "Error: no se encuentra nmcli (NetworkManager)."
    echo "Este script está pensado para Raspberry Pi OS Bookworm o posterior."
    exit 1
fi

echo "Configurando punto de acceso WiFi para Jarvis On Road..."
echo "  SSID: $SSID"
echo "  Interfaz: $IFACE"
echo "  IP: $IP_RANGE"

# Desactiva el AP existente si lo hay y lo elimina para evitar conflictos.
nmcli connection down "$CONN_NAME" >/dev/null 2>&1 || true
nmcli connection delete "$CONN_NAME" >/dev/null 2>&1 || true

# Crea el punto de acceso.
nmcli device wifi hotspot \
    ifname "$IFACE" \
    con-name "$CONN_NAME" \
    ssid "$SSID" \
    password "$PASSWORD" \
    band bg \
    channel 6

# Ajusta IP estática y DHCP local para los clientes.
# 'ipv4.method shared' activa un mini DHCP/DNS; si la Raspberry tiene otra
# conexión con internet, también la comparte. Si no la tiene, los clientes
# solo tendrán acceso local a Jarvis.
nmcli connection modify "$CONN_NAME" \
    ipv4.method shared \
    ipv4.addresses "$IP_RANGE" \
    autoconnect yes

nmcli connection up "$CONN_NAME"

echo ""
echo "Punto de acceso activado."
echo "Conecta tu móvil a la red WiFi '$SSID' con la contraseña que configuraste."
echo "Luego abre: http://${IP_RANGE%/*}:8000"
echo ""
echo "Para cambiar la contraseña más adelante, vuelve a ejecutar este script"
echo "o edita la variable JARVIS_AP_PASSWORD antes de llamarlo."
