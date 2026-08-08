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
from src.obd2.reader import OBD2Reader
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

    logger.info("Iniciando lector OBD-II...")
    reader = OBD2Reader()
    reader.start()

    logger.info("Inicializando controlador de LEDs...")
    led_controller = LEDController()
    if led_controller.enabled:
        logger.info("LEDs habilitados: %s", SETTINGS.led_mac)
    else:
        logger.info("LEDs deshabilitados.")

    app = create_app(reader, led_controller)

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
        logger.info("Sistema detenido.")


if __name__ == "__main__":
    main()
