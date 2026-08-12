"""Herramienta de descubrimiento de capacidades OBD-II.

Uso:
    python -m src.obd2.discovery

En Raspberry Pi (modo real) antes de conectar el vLinker:
    OBD_MOCK=false python -m src.obd2.discovery
"""

import argparse
import logging
import sys
from pathlib import Path

from src.config import SETTINGS
from src.obd2.connector import OBDConnection, PIDReading, create_obd_connection
from src.obd2.pids import PID_REGISTRY

logger = logging.getLogger(__name__)


def setup_logging(log_path: str, level: str) -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, mode="a", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _format_value(reading: PIDReading) -> str:
    if reading.value is None:
        return "-"
    return str(reading.value)


def discover(connection: OBDConnection, pids: list[str] | None = None) -> None:
    """Consulta PIDs de prueba e imprime un resumen del adaptador y ECU."""
    pids = pids or list(PID_REGISTRY.keys())

    print(f"\nConectado: {connection.is_connected()}")
    print(f"Protocolo : {connection.protocol_name() or 'desconocido'}")
    print(f"ECU       : {connection.ecu_address() or 'desconocida'}")
    print()

    header = f"{'PID':<8} {'NOMBRE':<25} {'VALOR':<12} {'UNIDAD':<8} {'ESTADO':<20} RAW"
    print(header)
    print("-" * len(header) + "---")

    for pid in pids:
        reading = connection.query_pid(pid)
        value_str = _format_value(reading)
        raw = (reading.raw_value or "")[:40]
        print(
            f"{reading.pid:<8} "
            f"{_pid_label(reading.pid):<25} "
            f"{value_str:<12} "
            f"{(reading.unit or ''):<8} "
            f"{reading.status:<20} "
            f"{raw}"
        )

    print()


def _pid_label(pid: str) -> str:
    from src.obd2.pids import get_pid_descriptor

    descriptor = get_pid_descriptor(pid)
    return descriptor.label if descriptor else pid


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descubre capacidades OBD-II del adaptador conectado."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=SETTINGS.obd_mock,
        help="Usa conexión simulada.",
    )
    parser.add_argument(
        "--port",
        default=SETTINGS.obd_port,
        help="Puerto serie del adaptador OBD-II.",
    )
    parser.add_argument(
        "--pids",
        default=",".join(SETTINGS.pids),
        help="Lista de PIDs separados por comas.",
    )
    args = parser.parse_args()

    setup_logging(SETTINGS.obd_log_path, SETTINGS.log_level)

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
        discover(connection, pids)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
