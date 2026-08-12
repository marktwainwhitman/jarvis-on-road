"""Collector autónomo de datos OBD-II.

Lee periódicamente los PIDs configurados y los persiste en archivos CSV diarios
bajo ``data/obd/``. También registra eventos importantes en ``logs/jarvis.log``.

Punto de entrada:
    python -m src.obd2.collector

El collector reutiliza ``OBD2Reader`` para aprovechar la lógica de reconexión y
backoff, por lo que es seguro ejecutarlo en la Raspberry sin supervisión.
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional

from src.config import SETTINGS
from src.obd2.connector import PIDReading, create_obd_connection
from src.obd2.csv_logger import CSVLogger
from src.obd2.discovery import discover
from src.obd2.reader import OBD2Reader

logger = logging.getLogger(__name__)


class OBDCollector:
    """Orquesta la lectura periódica y el volcado a CSV."""

    def __init__(
        self,
        reader: OBD2Reader,
        csv_logger: CSVLogger,
    ):
        self._reader = reader
        self._csv_logger = csv_logger
        self._running = False

    def start(self) -> None:
        logger.info("Iniciando collector OBD-II...")
        self._running = True
        self._reader.start()

    def stop(self) -> None:
        logger.info("Deteniendo collector OBD-II...")
        self._running = False
        self._reader.stop()
        self._csv_logger.close()
        logger.info("Collector detenido.")

    def run_forever(self) -> None:
        self.start()
        try:
            while self._running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("Interrupción recibida.")
        finally:
            self.stop()


def _on_readings(csv_logger: CSVLogger, readings: List[PIDReading]) -> None:
    """Callback que recibe las lecturas enriquecidas y las escribe a CSV."""
    try:
        csv_logger.write(readings)
    except Exception:
        logger.exception("Error escribiendo lecturas en CSV")


def setup_logging(log_path: str, level: str) -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(level.upper())
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collector autónomo OBD-II para Jarvis On Road."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=SETTINGS.obd_mock,
        help="Usa conexión simulada en lugar de Bluetooth real.",
    )
    parser.add_argument(
        "--port",
        default=SETTINGS.obd_port,
        help="Puerto serie del adaptador OBD-II (p. ej. /dev/rfcomm0).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=SETTINGS.read_interval,
        help="Segundos entre lecturas.",
    )
    parser.add_argument(
        "--csv-dir",
        default=SETTINGS.obd_csv_dir,
        help="Directorio donde se guardan los CSV diarios.",
    )
    parser.add_argument(
        "--log",
        default=SETTINGS.obd_log_path,
        help="Ruta del archivo de log.",
    )
    parser.add_argument(
        "--pids",
        default=",".join(SETTINGS.pids),
        help="Lista de PIDs separados por comas.",
    )
    parser.add_argument(
        "--no-discovery",
        action="store_true",
        help="Omitir el descubrimiento inicial.",
    )
    args = parser.parse_args()

    setup_logging(args.log, SETTINGS.log_level)

    pids = [pid.strip() for pid in args.pids.split(",") if pid.strip()]

    connection = create_obd_connection(
        port=args.port,
        pids=pids,
        mock=args.mock,
        protocol=SETTINGS.obd_protocol or None,
        timeout=SETTINGS.obd_timeout,
        fast=SETTINGS.obd_fast,
    )
    try:
        if not args.no_discovery:
            discover(connection, pids)
    finally:
        connection.close()

    csv_logger = CSVLogger(args.csv_dir, pids=pids)
    reader = OBD2Reader(
        connection=None,
        on_readings=lambda readings: _on_readings(csv_logger, readings),
    )
    reader._pids = pids
    reader._interval = args.interval

    collector = OBDCollector(reader, csv_logger)

    def _signal_handler(signum, frame):
        logger.info("Señal %s recibida, deteniendo collector...", signum)
        collector.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _signal_handler)

    collector.run_forever()


if __name__ == "__main__":
    main()
