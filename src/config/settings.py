"""Configuración centralizada de Jarvis On Road."""

import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Settings:
    """Configuración del sistema."""

    obd_port: str = os.getenv("OBD_PORT", "")
    obd_mock: bool = os.getenv("OBD_MOCK", "true").lower() in ("1", "true", "yes")
    read_interval: float = float(os.getenv("OBD_READ_INTERVAL", "1.0"))
    dtc_interval: float = float(os.getenv("OBD_DTC_INTERVAL", "30.0"))
    obd_reconnect_interval: float = float(os.getenv("OBD_RECONNECT_INTERVAL", "10.0"))
    obd_max_reconnect_interval: float = float(os.getenv("OBD_MAX_RECONNECT_INTERVAL", "300.0"))
    led_enabled: bool = os.getenv("LED_ENABLED", "false").lower() in ("1", "true", "yes")
    led_mac: str = os.getenv("LED_MAC", "")
    led_ble_timeout: float = float(os.getenv("LED_BLE_TIMEOUT", "15.0"))
    host: str = os.getenv("JARVIS_HOST", "0.0.0.0")
    port: int = int(os.getenv("JARVIS_PORT", "8000"))
    log_level: str = os.getenv("JARVIS_LOG_LEVEL", "info")

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
