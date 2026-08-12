"""Lector periódico de datos OBD-II."""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from src.config import SETTINGS
from src.obd2.alerts import evaluate
from src.obd2.connector import OBDConnection, PIDReading, create_obd_connection

logger = logging.getLogger(__name__)


class OBD2Reader:
    """Lee PIDs de forma periódica y guarda la última muestra."""

    def __init__(
        self,
        connection: OBDConnection = None,
        on_sample: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_readings: Optional[Callable[[List[PIDReading]], None]] = None,
    ):
        # Si se inyecta una conexión (p. ej. en tests) se usa tal cual y no se
        # gestiona su reconexión automática. Si no, la conexión se crea de
        # forma perezosa dentro del hilo del lector para no bloquear el
        # arranque de la aplicación si el adaptador OBD-II no responde.
        self._connection = connection
        self._manage_connection = connection is None
        # Callbacks opcionales invocados con cada muestra leída. Nunca deben
        # bloquear ni propagar excepciones al hilo lector.
        self._on_sample = on_sample
        self._on_readings = on_readings
        self._interval = SETTINGS.read_interval
        self._dtc_interval = SETTINGS.dtc_interval
        self._reconnect_interval = SETTINGS.obd_reconnect_interval
        self._max_reconnect_interval = SETTINGS.obd_max_reconnect_interval
        self._pids = SETTINGS.pids
        self._latest_data: Dict[str, Any] = {"dtcs": [], "connected": False}
        self._last_update: str = ""
        self._last_dtc_read: float = 0.0
        self._last_connect_attempt: float = 0.0
        self._consecutive_failures = 0
        self._running = False
        self._thread: threading.Thread | None = None
        # Protege el cache de muestras leidas por el hilo lector y consultado
        # por el event loop de FastAPI.
        self._lock = threading.Lock()
        # Protege el acceso a self._connection (cierre, reconexion y lecturas).
        self._conn_lock = threading.Lock()

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
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning(
                    "El hilo lector OBD-II no finalizó limpiamente tras 5s."
                )
        with self._conn_lock:
            if self._connection is not None:
                try:
                    self._connection.close()
                except Exception:
                    logger.exception("Error cerrando conexión OBD-II al detener")
                self._connection = None
        logger.info("Lector OBD-II detenido.")

    def _loop(self) -> None:
        while self._running:
            self._try_connect()

            with self._conn_lock:
                if self._connection is not None:
                    sample = self._read_sample_locked()
                else:
                    sample = {"connected": False, "dtcs": []}
                with self._lock:
                    self._latest_data = sample
                    self._last_update = datetime.now(timezone.utc).isoformat()

            if self._on_sample is not None:
                try:
                    self._on_sample(sample)
                except Exception:
                    logger.exception("Error en callback on_sample")
            time.sleep(self._interval)

    def _try_connect(self) -> None:
        if not self._manage_connection:
            return
        now = time.time()
        # Backoff exponencial: empieza en reconnect_interval y duplica en cada
        # fallo consecutivo hasta max_reconnect_interval.
        backoff = min(
            self._reconnect_interval * (2 ** max(0, self._consecutive_failures - 1)),
            self._max_reconnect_interval,
        )
        if now - self._last_connect_attempt < backoff:
            return
        self._last_connect_attempt = now
        with self._conn_lock:
            try:
                if self._connection is not None:
                    try:
                        self._connection.close()
                    except Exception:
                        logger.exception("Error cerrando conexión OBD-II previa")
                self._connection = create_obd_connection(
                    port=SETTINGS.obd_port,
                    pids=self._pids,
                    mock=SETTINGS.obd_mock,
                    protocol=SETTINGS.obd_protocol or None,
                    timeout=SETTINGS.obd_timeout,
                    fast=SETTINGS.obd_fast,
                )
                self._consecutive_failures = 0
                logger.info("Conexión OBD-II establecida.")
            except Exception:
                self._consecutive_failures += 1
                logger.exception(
                    "No se pudo conectar a OBD-II; reintentando en %.0fs",
                    min(
                        self._reconnect_interval
                        * (2 ** max(0, self._consecutive_failures - 1)),
                        self._max_reconnect_interval,
                    ),
                )
                self._connection = None

    def _read_sample_locked(self) -> Dict[str, Any]:
        # Debe llamarse con self._conn_lock adquirido.
        sample: Dict[str, Any] = {"connected": self._connection.is_connected()}
        readings: List[PIDReading] = []
        for pid in self._pids:
            try:
                reading = self._connection.query_pid(pid)
                readings.append(reading)
                sample[pid] = _serialize_value(reading.value)
            except Exception:
                logger.exception("Error leyendo PID %s", pid)
                sample[pid] = None

        if self._on_readings is not None:
            try:
                self._on_readings(readings)
            except Exception:
                logger.exception("Error en callback on_readings")

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
        with self._conn_lock:
            if self._connection is None:
                return {
                    "connected": False,
                    "port": SETTINGS.obd_port,
                    "pids": self._pids,
                }
            return self._connection.status()


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "magnitude"):
        return value.magnitude
    if hasattr(value, "value"):
        return value.value
    return value
