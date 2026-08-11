"""Registro histórico de lecturas OBD-II para estadísticas y análisis preventivo.

Estrategia de retención (pensada para tarjetas SD limitadas, p. ej. 64 GB):

- Las lecturas en crudo (``readings``, un valor por PID y ciclo de lectura)
  solo se conservan ``retention_days`` días. Con 6 PIDs a 1 lectura/segundo
  esto son varios GB al mes, así que no tiene sentido guardarlas para
  siempre.
- Cada hora se agregan (min/máx/media) en ``hourly_stats``, que sí se
  conserva indefinidamente: son unas pocas decenas de miles de filas al año,
  tamaño despreciable, y es la fuente adecuada para tendencias a medio/largo
  plazo y análisis preventivo.
- Los cambios de estado relevantes (alertas que empiezan/terminan, códigos
  DTC nuevos) se registran en ``events``, evitando duplicar una fila por
  cada ciclo de lectura mientras la alerta esté activa.

Las escrituras se bufferizan en memoria y se vuelcan a SQLite en lotes desde
un hilo de fondo, para no bloquear el hilo lector de OBD-II con I/O de disco
y para reducir el desgaste de escritura de la tarjeta SD.
"""

import logging
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from src.obd2.alerts import evaluate

from .database import connect, init_schema

logger = logging.getLogger(__name__)

IGNORED_KEYS = {"connected", "_last_update", "alerts"}

HOUR_SECONDS = 3600


def _to_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class HistoryStore:
    """Guarda muestras OBD-II en SQLite y expone consultas para la API."""

    def __init__(
        self,
        db_path: str,
        retention_days: int = 30,
        flush_interval: float = 5.0,
    ):
        self._db_path = db_path
        self._retention_days = retention_days
        self._flush_interval = flush_interval

        self._buffer: List[tuple] = []
        self._buffer_lock = threading.Lock()

        self._last_alert_level: Dict[str, str] = {}
        self._last_dtc_codes: set = set()

        self._last_rollup_hour: Optional[int] = None

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Conexión propia del hilo de escritura; las consultas de lectura
        # abren conexiones cortas propias (ver _connect_readonly).
        self._write_conn: Optional[sqlite3.Connection] = None

    # -- ciclo de vida -----------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._write_conn = connect(self._db_path)
        init_schema(self._write_conn)
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("HistoryStore iniciado (db=%s, retención=%sd).", self._db_path, self._retention_days)

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._flush()
        if self._write_conn is not None:
            self._write_conn.close()
            self._write_conn = None
        logger.info("HistoryStore detenido.")

    def _loop(self) -> None:
        while self._running:
            # Espera interrumpible: permite que stop() no bloquee hasta el
            # próximo flush_interval completo.
            if self._stop_event.wait(timeout=self._flush_interval):
                break
            try:
                self._flush()
                self._maybe_rollup()
            except Exception:
                logger.exception("Error en el ciclo de persistencia de historial")

    # -- ingesta -------------------------------------------------------------

    def record(self, sample: Dict[str, Any]) -> None:
        """Encola una muestra leída por el `OBD2Reader`. Seguro de llamar
        desde el hilo lector: no bloquea en I/O de disco.
        """
        try:
            ts = int(time.time())
            rows = []
            for pid, raw_value in sample.items():
                if pid in IGNORED_KEYS or pid == "dtcs":
                    continue
                value = _to_float(raw_value)
                if value is not None:
                    rows.append((ts, pid, value))
            if rows:
                with self._buffer_lock:
                    self._buffer.extend(rows)

            self._record_events(ts, sample)
        except Exception:
            logger.exception("Error registrando muestra en el historial")

    def _record_events(self, ts: int, sample: Dict[str, Any]) -> None:
        alerts = evaluate(sample)
        for pid, status in alerts["pids"].items():
            level = status["level"]
            previous = self._last_alert_level.get(pid, "ok")
            if level != previous and level in ("warning", "critical"):
                self._queue_event(
                    ts, "alert", pid=pid, level=level, message=status.get("message")
                )
            self._last_alert_level[pid] = level

        dtcs = sample.get("dtcs") or []
        codes = {d.get("code") for d in dtcs if isinstance(d, dict) and d.get("code")}
        for code in codes - self._last_dtc_codes:
            description = next(
                (d.get("description") for d in dtcs if d.get("code") == code), None
            )
            self._queue_event(ts, "dtc", code=code, message=description)
        self._last_dtc_codes = codes

    def _queue_event(
        self,
        ts: int,
        event_type: str,
        pid: Optional[str] = None,
        level: Optional[str] = None,
        code: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        with self._buffer_lock:
            self._buffer.append(("__event__", ts, event_type, pid, level, code, message))

    # -- persistencia ---------------------------------------------------------

    def _flush(self) -> None:
        if self._write_conn is None:
            return
        with self._buffer_lock:
            if not self._buffer:
                return
            batch = self._buffer
            self._buffer = []

        readings = [row for row in batch if row[0] != "__event__"]
        events = [row[1:] for row in batch if row[0] == "__event__"]

        try:
            if readings:
                self._write_conn.executemany(
                    "INSERT INTO readings (ts, pid, value) VALUES (?, ?, ?)", readings
                )
            if events:
                self._write_conn.executemany(
                    "INSERT INTO events (ts, type, pid, level, code, message) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    events,
                )
            self._write_conn.commit()
        except Exception:
            logger.exception("Error volcando historial a SQLite")
            self._write_conn.rollback()

    def _maybe_rollup(self) -> None:
        current_hour = int(time.time()) // HOUR_SECONDS
        if self._last_rollup_hour is None:
            self._last_rollup_hour = current_hour
            return
        if current_hour == self._last_rollup_hour:
            return

        # Agrega todas las horas completas transcurridas desde la última vez
        # (cubre el caso de que la app haya estado parada varias horas).
        for hour in range(self._last_rollup_hour, current_hour):
            self._rollup_hour(hour)
        self._purge_old_readings()
        self._last_rollup_hour = current_hour

    def _rollup_hour(self, hour: int) -> None:
        hour_ts = hour * HOUR_SECONDS
        start, end = hour_ts, hour_ts + HOUR_SECONDS
        try:
            self._write_conn.execute(
                """
                INSERT INTO hourly_stats (pid, hour_ts, min_value, max_value, avg_value, sample_count)
                SELECT pid, ?, MIN(value), MAX(value), AVG(value), COUNT(*)
                FROM readings
                WHERE ts >= ? AND ts < ?
                GROUP BY pid
                ON CONFLICT(pid, hour_ts) DO UPDATE SET
                    min_value = excluded.min_value,
                    max_value = excluded.max_value,
                    avg_value = excluded.avg_value,
                    sample_count = excluded.sample_count
                """,
                (hour_ts, start, end),
            )
            self._write_conn.commit()
        except Exception:
            logger.exception("Error agregando estadísticas horarias")
            self._write_conn.rollback()

    def _purge_old_readings(self) -> None:
        cutoff = int(time.time()) - self._retention_days * 24 * HOUR_SECONDS
        try:
            self._write_conn.execute("DELETE FROM readings WHERE ts < ?", (cutoff,))
            self._write_conn.commit()
        except Exception:
            logger.exception("Error purgando lecturas antiguas")
            self._write_conn.rollback()

    # -- consultas (usadas por la API) -----------------------------------------

    def _connect_readonly(self) -> sqlite3.Connection:
        conn = connect(self._db_path)
        init_schema(conn)
        return conn

    def get_readings(self, pid: str, since_ts: float, limit: int = 5000) -> List[Dict[str, Any]]:
        conn = self._connect_readonly()
        try:
            cur = conn.execute(
                "SELECT ts, value FROM readings WHERE pid = ? AND ts >= ? "
                "ORDER BY ts ASC LIMIT ?",
                (pid, int(since_ts), limit),
            )
            return [{"ts": ts, "value": value} for ts, value in cur.fetchall()]
        finally:
            conn.close()

    def get_hourly_stats(self, pid: str, since_ts: float) -> List[Dict[str, Any]]:
        conn = self._connect_readonly()
        try:
            cur = conn.execute(
                "SELECT hour_ts, min_value, max_value, avg_value, sample_count "
                "FROM hourly_stats WHERE pid = ? AND hour_ts >= ? ORDER BY hour_ts ASC",
                (pid, int(since_ts)),
            )
            return [
                {
                    "ts": hour_ts,
                    "min": min_value,
                    "max": max_value,
                    "avg": avg_value,
                    "count": count,
                }
                for hour_ts, min_value, max_value, avg_value, count in cur.fetchall()
            ]
        finally:
            conn.close()

    def get_events(
        self, since_ts: float, event_type: Optional[str] = None, limit: int = 500
    ) -> List[Dict[str, Any]]:
        conn = self._connect_readonly()
        try:
            if event_type:
                cur = conn.execute(
                    "SELECT ts, type, pid, level, code, message FROM events "
                    "WHERE ts >= ? AND type = ? ORDER BY ts DESC LIMIT ?",
                    (int(since_ts), event_type, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT ts, type, pid, level, code, message FROM events "
                    "WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
                    (int(since_ts), limit),
                )
            return [
                {
                    "ts": ts,
                    "type": type_,
                    "pid": pid,
                    "level": level,
                    "code": code,
                    "message": message,
                }
                for ts, type_, pid, level, code, message in cur.fetchall()
            ]
        finally:
            conn.close()
