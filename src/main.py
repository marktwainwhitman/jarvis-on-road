"""Punto de entrada principal de Jarvis On Road."""

import logging
import socket
import sys
from pathlib import Path

# Asegura que el repo raíz está en sys.path para imports absolutos tipo src.*
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import uvicorn

from src.config import SETTINGS
from src.leds.controller import LEDController
from src.leds.scheduler import DayNightScheduler
from src.obd2.reader import OBD2Reader
from src.storage.history import HistoryStore
from src.web.server import create_app

__version__ = "0.2.0"

logging.basicConfig(
    level=SETTINGS.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Inicia la aplicación Jarvis On Road."""
    print("Jarvis On Road iniciando...")
    print(f"Versión {__version__}")
    print(f"Ejecutando en: {socket.gethostname()}")

    logger.info("Iniciando histórico de datos OBD-II (%s)...", SETTINGS.db_path)
    history_store = HistoryStore(
        db_path=SETTINGS.db_path, retention_days=SETTINGS.db_retention_days
    )
    try:
        history_store.start()
    except Exception:
        # No dejamos que un fallo de SQLite (permisos, disco lleno, ruta no
        # escribible...) tire toda la aplicación: seguimos sin histórico y
        # los endpoints /api/obd/history, /stats y /events responderán 503.
        logger.exception(
            "No se pudo iniciar el histórico SQLite en %s; Jarvis seguirá "
            "funcionando sin histórico ni estadísticas.",
            SETTINGS.db_path,
        )
        history_store = None

    logger.info("Iniciando lector OBD-II...")
    reader = OBD2Reader(on_sample=history_store.record if history_store else None)
    reader.start()

    logger.info("Inicializando controlador de LEDs...")
    led_controller = LEDController()
    if led_controller.enabled:
        logger.info("LEDs habilitados: %s", SETTINGS.led_mac)
    else:
        logger.info("LEDs deshabilitados.")

    led_scheduler = DayNightScheduler(
        led_controller,
        latitude=SETTINGS.led_auto_lat,
        longitude=SETTINGS.led_auto_lon,
        timezone=SETTINGS.led_auto_timezone,
        check_interval=SETTINGS.led_auto_check_interval,
        auto_enabled=SETTINGS.led_auto_enabled,
        pre_light_minutes=SETTINGS.led_auto_pre_light_minutes,
    )
    if led_scheduler.auto_enabled:
        logger.info("Automatización día/noche de LEDs activada.")

    app = create_app(reader, led_controller, history_store, led_scheduler)

    logger.info(
        "Servidor web disponible en http://%s:%s", SETTINGS.host, SETTINGS.port
    )
    try:
        uvicorn.run(
            app,
            host=SETTINGS.host,
            port=SETTINGS.port,
            log_level=SETTINGS.log_level,
        )
    except KeyboardInterrupt:
        logger.info("Interrupción recibida, cerrando...")
    finally:
        reader.stop()
        if history_store:
            history_store.stop()
        logger.info("Sistema detenido.")


if __name__ == "__main__":
    main()
