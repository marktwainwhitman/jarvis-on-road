"""Configuración centralizada de Jarvis On Road."""

import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Settings:
    """Configuración del sistema."""

    obd_port: str = os.getenv("OBD_PORT", "")
    obd_mock: bool = os.getenv("OBD_MOCK", "true").lower() in ("1", "true", "yes")
    # Protocolo OBD a forzar con python-obd. Para Kia Ceed 2025 (CAN 11-bit 500 kbaud)
    # usar "6". Dejar vacío para autodetección (más lento, menos fiable en algunos
    # adaptadores). Valores posibles: "1".."A".
    obd_protocol: str = os.getenv("OBD_PROTOCOL", "6")
    obd_fast: bool = os.getenv("OBD_FAST", "false").lower() in ("1", "true", "yes")
    obd_timeout: float = float(os.getenv("OBD_TIMEOUT", "30"))
    read_interval: float = float(os.getenv("OBD_READ_INTERVAL", "1.0"))
    dtc_interval: float = float(os.getenv("OBD_DTC_INTERVAL", "30.0"))
    obd_reconnect_interval: float = float(os.getenv("OBD_RECONNECT_INTERVAL", "10.0"))
    obd_max_reconnect_interval: float = float(os.getenv("OBD_MAX_RECONNECT_INTERVAL", "300.0"))
    obd_csv_dir: str = os.getenv("OBD_CSV_DIR", "data/obd")
    obd_log_path: str = os.getenv("OBD_LOG_PATH", "logs/jarvis.log")
    led_enabled: bool = os.getenv("LED_ENABLED", "false").lower() in ("1", "true", "yes")
    led_mac: str = os.getenv("LED_MAC", "")
    led_ble_timeout: float = float(os.getenv("LED_BLE_TIMEOUT", "15.0"))

    # Automatización día/noche de los LEDs (amanecer/atardecer calculado).
    # Ubicación por defecto aproximada a la zona Huelva-Sevilla-Cádiz; con un
    # margen de error de ~30 min es suficiente, no requiere GPS.
    led_auto_enabled: bool = os.getenv("LED_AUTO_MODE", "false").lower() in ("1", "true", "yes")
    led_auto_lat: float = float(os.getenv("LED_AUTO_LAT", "37.2"))
    led_auto_lon: float = float(os.getenv("LED_AUTO_LON", "-6.4"))
    led_auto_timezone: str = os.getenv("LED_AUTO_TZ", "Europe/Madrid")
    led_auto_check_interval: float = float(os.getenv("LED_AUTO_CHECK_INTERVAL", "60.0"))
    # Minutos que se anticipa el encendido respecto al atardecer real (el
    # apagado sigue ocurriendo en el amanecer real).
    led_auto_pre_light_minutes: float = float(os.getenv("LED_AUTO_PRE_LIGHT_MINUTES", "30.0"))
    host: str = os.getenv("JARVIS_HOST", "0.0.0.0")
    port: int = int(os.getenv("JARVIS_PORT", "8000"))
    log_level: str = os.getenv("JARVIS_LOG_LEVEL", "info")
    db_path: str = os.getenv("JARVIS_DB_PATH", "data/jarvis.db")
    db_retention_days: int = int(os.getenv("JARVIS_DB_RETENTION_DAYS", "30"))

    # Lista de PIDs que se intentarán leer en cada ciclo.
    pids: Optional[List[str]] = None

    def __post_init__(self):
        if self.pids is None:
            object.__setattr__(
                self,
                "pids",
                [
                    pid.strip()
                    for pid in os.getenv(
                        "OBD_PIDS",
                        "RPM,SPEED,COOLANT_TEMP,ENGINE_LOAD,THROTTLE_POS,INTAKE_TEMP",
                    ).split(",")
                    if pid.strip()
                ],
            )


SETTINGS = Settings()
