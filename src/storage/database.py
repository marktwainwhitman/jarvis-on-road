"""Conexión y esquema de la base de datos SQLite de Jarvis On Road."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    pid TEXT NOT NULL,
    value REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_pid_ts ON readings(pid, ts);

CREATE TABLE IF NOT EXISTS hourly_stats (
    pid TEXT NOT NULL,
    hour_ts INTEGER NOT NULL,
    min_value REAL NOT NULL,
    max_value REAL NOT NULL,
    avg_value REAL NOT NULL,
    sample_count INTEGER NOT NULL,
    PRIMARY KEY (pid, hour_ts)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    type TEXT NOT NULL,
    pid TEXT,
    level TEXT,
    code TEXT,
    message TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""


def connect(db_path: str) -> sqlite3.Connection:
    """Abre una conexión a la base de datos, creando el directorio si falta.

    Usa WAL para permitir lecturas concurrentes mientras se escribe (la web
    consulta historial/stats mientras el hilo lector sigue insertando), y
    reduce el número de fsync en la tarjeta SD.
    """
    path = Path(db_path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=5.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
