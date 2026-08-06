"""Lector periódico de datos OBD-II."""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict

from src.config import SETTINGS
from src.obd2.alerts import evaluate
from src.obd2.connector import OBD2Connection, create_connection

logger = logging.getLogger(__name__)


class OBD2Reader:
    """Lee PIDs de forma periódica y guarda la última muestra."""

    def __init__(self, connection: OBD2Connection = None):
        # Si se inyecta una conexión (p. ej. en tests) se usa tal cual y no se
        # gestiona su reconexión automática. Si no, la conexión se crea de
        # forma perezosa dentro del hilo del lector para no bloquear el
        # arranque de la aplicación si el adaptador OBD-II no responde.
        self._connection = connection
        self._manage_connection = connection is None
        self._interval = SETTINGS.read_interval
        self._dtc_interval = SETTINGS.dtc_interval
        self._reconnect_interval = SETTINGS.obd_reconnect_interval
        self._pids = SETTINGS.pids
        self._latest_data: Dict[str, Any] = {"dtcs": [], "connected": False}
        self._last_update: str = ""
        self._last_dtc_read: float = 0.0
        self._last_connect_attempt: float = 0.0
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Lector OBD-II iniciado (intervalo=%ss).", self._interval)

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self._connection is not None:
            self._connection.close()
        logger.info("Lector OBD-II detenido.")

    def _loop(self) -> None:
        while self._running:
            if self._connection is None or not self._connection.is_connected():
                self._try_connect()

            if self._connection is not None:
                sample = self._read_sample()
                with self._lock:
                    self._latest_data = sample
                    self._last_update = datetime.now(timezone.utc).isoformat()
            time.sleep(self._interval)

    def _try_connect(self) -> None:
        if not self._manage_connection:
            return
        now = time.time()
        if now - self._last_connect_attempt < self._reconnect_interval:
            return
        self._last_connect_attempt = now
        try:
            if self._connection is not None:
                try:
                    self._connection.close()
                except Exception:
                    logger.exception("Error cerrando conexión OBD-II previa")
            self._connection = create_connection(
                SETTINGS.obd_port, self._pids, mock=SETTINGS.obd_mock
            )
            logger.info("Conexión OBD-II establecida.")
        except Exception:
            logger.exception(
                "No se pudo conectar a OBD-II; reintentando en %ss",
                self._reconnect_interval,
            )
            self._connection = None

    def _read_sample(self) -> Dict[str, Any]:
        sample: Dict[str, Any] = {"connected": self._connection.is_connected()}
        for pid in self._pids:
            try:
                value = self._connection.query(pid)
                sample[pid] = _serialize_value(value)
            except Exception:
                logger.exception("Error leyendo PID %s", pid)
                sample[pid] = None

        now = time.time()
        if now - self._last_dtc_read >= self._dtc_interval:
            try:
                dtcs = self._connection.get_dtcs()
                sample["dtcs"] = [
                    {"code": code, "description": desc or "Descripción no disponible"}
                    for code, desc in dtcs
                ]
                self._last_dtc_read = now
            except Exception:
                logger.exception("Error leyendo códigos DTC")
                sample["dtcs"] = self._latest_data.get("dtcs", [])
        else:
            sample["dtcs"] = self._latest_data.get("dtcs", [])

        return sample

    def get_latest(self) -> Dict[str, Any]:
        with self._lock:
            snapshot = {
                **self._latest_data,
                "_last_update": self._last_update,
            }
        snapshot["alerts"] = evaluate(snapshot)
        return snapshot

    def get_status(self) -> Dict[str, Any]:
        if self._connection is None:
            return {"connected": False, "port": SETTINGS.obd_port, "pids": self._pids}
        return self._connection.status()


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "magnitude"):
        return value.magnitude
    if hasattr(value, "value"):
        return value.value
    return value
