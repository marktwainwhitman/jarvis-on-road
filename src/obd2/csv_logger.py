"""Registro de lecturas OBD-II en archivos CSV planos.

Cada día se escribe un archivo distinto bajo ``data/obd/YYYY-MM-DD.csv``.
El formato es *largo* (una fila por lectura de PID) para que sea trivial
añadir o quitar PIDs sin cambiar el esquema de columnas.

Columnas:
- timestamp: ISO 8601 con zona UTC.
- pid: nombre corto del PID (p. ej. ``RPM``).
- name: descripción legible (p. ej. ``Engine RPM``).
- value: valor numérico escalar, o cadena vacía si no disponible.
- unit: unidad de medida.
- status: VALID, ZERO, UNAVAILABLE, UNSUPPORTED o COMMUNICATION_ERROR.
- ecu: identificador de la ECU que respondió (p. ej. ``0x7E8``).
- raw_value: trama RAW de respuesta, si se ha conservado.
"""

import csv
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.obd2.connector import PIDReading

logger = logging.getLogger(__name__)

FIELDNAMES = [
    "timestamp",
    "pid",
    "name",
    "value",
    "unit",
    "status",
    "ecu",
    "raw_value",
]


class CSVLogger:
    """Escribe lecturas OBD-II en archivos CSV diarios."""

    def __init__(self, directory: Path | str, pids: Optional[List[str]] = None):
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._pids = pids
        self._lock = threading.Lock()
        self._current_path: Optional[Path] = None
        self._current_file: Optional[object] = None
        self._current_writer: Optional[csv.DictWriter] = None

    def write(self, readings: List[PIDReading]) -> None:
        """Escribe una lista de lecturas en el CSV del día actual."""
        if not readings:
            return

        now = datetime.now(timezone.utc)
        path = self._path_for(now.date())

        with self._lock:
            if self._current_path != path:
                self._rotate(path)

            for reading in readings:
                self._write_row(reading, now)

    def close(self) -> None:
        """Cierra el archivo CSV abierto, si lo hay."""
        with self._lock:
            if self._current_file is not None:
                try:
                    self._current_file.close()
                except Exception:
                    logger.exception("Error cerrando archivo CSV")
                self._current_file = None
                self._current_writer = None
                self._current_path = None

    def _path_for(self, date) -> Path:
        return self._directory / f"{date.isoformat()}.csv"

    def _rotate(self, path: Path) -> None:
        if self._current_file is not None:
            try:
                self._current_file.close()
            except Exception:
                logger.exception("Error cerrando archivo CSV anterior")
        self._current_path = path
        file_exists = self._current_path.exists() and self._current_path.stat().st_size > 0
        # utf-8-sig para que Excel abra correctamente caracteres UTF-8.
        self._current_file = open(
            self._current_path, "a", newline="", encoding="utf-8-sig"
        )
        self._current_writer = csv.DictWriter(
            self._current_file, fieldnames=FIELDNAMES
        )
        if not file_exists:
            self._current_writer.writeheader()
            self._current_file.flush()
            logger.info("Creado archivo CSV de registro: %s", self._current_path)
        else:
            self._current_file.flush()

    def _write_row(self, reading: PIDReading, ts: datetime) -> None:
        if self._current_writer is None:
            return
        self._current_writer.writerow(
            {
                "timestamp": ts.isoformat(),
                "pid": reading.pid,
                "name": _pid_name(reading.pid),
                "value": "" if reading.value is None else reading.value,
                "unit": reading.unit or "",
                "status": reading.status,
                "ecu": reading.ecu or "",
                "raw_value": reading.raw_value or "",
            }
        )
        self._current_file.flush()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def _pid_name(pid: str) -> str:
    from src.obd2.pids import get_pid_descriptor

    descriptor = get_pid_descriptor(pid)
    return descriptor.label if descriptor else pid
