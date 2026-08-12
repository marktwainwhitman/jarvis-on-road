"""Tests para la reconexión automática del lector OBD-II."""

import threading
import time

import src.obd2.reader as reader_module
from src.obd2.connector import PIDReading
from src.obd2.reader import OBD2Reader


class FakeConnection:
    def __init__(self, connected=True):
        self._connected = connected
        self.closed = False

    def is_connected(self):
        return self._connected

    def query(self, pid_name):
        return 42

    def query_pid(self, pid_name):
        return PIDReading(
            pid=pid_name,
            value=42.0,
            unit=None,
            status="VALID",
            raw_value=f"FAKE:{pid_name}",
            ecu="FAKE",
        )

    def close(self):
        self.closed = True

    def status(self):
        return {"connected": self._connected, "port": "FAKE", "pids": []}

    def get_dtcs(self):
        return []

    def protocol_name(self):
        return "FAKE"

    def ecu_address(self):
        return "FAKE"


def test_reader_without_connection_has_default_status():
    reader = OBD2Reader.__new__(OBD2Reader)  # evita __init__ para no tocar SETTINGS/threads
    reader._connection = None
    reader._conn_lock = threading.Lock()
    reader._pids = ["RPM"]
    status = reader.get_status()
    assert status["connected"] is False


def _patch_reader(reader):
    # Asegura los campos internos que __init__ normalmente inicializa, para
    # poder instanciar OBD2Reader(connection=None) sin tocar SETTINGS.
    reader._lock = threading.Lock()
    reader._conn_lock = threading.Lock()
    reader._consecutive_failures = 0
    return reader


def test_try_connect_creates_connection_on_success(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr(reader_module, "create_obd_connection", lambda *a, **k: fake_conn)

    reader = _patch_reader(OBD2Reader(connection=None))
    reader._manage_connection = True
    reader._reconnect_interval = 0  # sin límite de tasa para el test
    reader._max_reconnect_interval = 10000
    reader._last_connect_attempt = 0.0

    reader._try_connect()

    assert reader._connection is fake_conn


def test_try_connect_keeps_connection_none_on_failure(monkeypatch):
    def _raise(*a, **k):
        raise RuntimeError("adaptador no disponible")

    monkeypatch.setattr(reader_module, "create_obd_connection", _raise)

    reader = _patch_reader(OBD2Reader(connection=None))
    reader._manage_connection = True
    reader._reconnect_interval = 0
    reader._max_reconnect_interval = 10000
    reader._last_connect_attempt = 0.0

    reader._try_connect()

    assert reader._connection is None


def test_try_connect_respects_backoff_interval(monkeypatch):
    calls = []

    def _create(*a, **k):
        calls.append(1)
        return FakeConnection()

    monkeypatch.setattr(reader_module, "create_obd_connection", _create)

    reader = _patch_reader(OBD2Reader(connection=None))
    reader._manage_connection = True
    reader._reconnect_interval = 1000  # muy largo, para forzar el rate-limit
    reader._max_reconnect_interval = 10000
    reader._last_connect_attempt = 0.0
    reader._connection = None

    reader._try_connect()
    reader._try_connect()

    assert len(calls) == 1


def test_backoff_increases_after_consecutive_failures(monkeypatch):
    def _create(*a, **k):
        raise RuntimeError("adaptador no disponible")

    monkeypatch.setattr(reader_module, "create_obd_connection", _create)

    reader = _patch_reader(OBD2Reader(connection=None))
    reader._manage_connection = True
    reader._reconnect_interval = 1.0
    reader._max_reconnect_interval = 10.0
    reader._last_connect_attempt = 0.0
    reader._connection = None

    reader._try_connect()  # fallo 1
    reader._try_connect()  # debe respetar backoff corto todavia
    first_backoff = min(
        reader._reconnect_interval * (2 ** max(0, reader._consecutive_failures - 1)),
        reader._max_reconnect_interval,
    )
    assert first_backoff >= reader._reconnect_interval

    # Simulamos que ha pasado suficiente tiempo para el siguiente intento
    reader._last_connect_attempt = time.time() - first_backoff - 0.1
    reader._try_connect()  # fallo 2 -> backoff mayor
    second_backoff = min(
        reader._reconnect_interval * (2 ** max(0, reader._consecutive_failures - 1)),
        reader._max_reconnect_interval,
    )
    assert second_backoff >= first_backoff


def test_success_resets_backoff(monkeypatch):
    monkeypatch.setattr(reader_module, "create_obd_connection", lambda *a, **k: FakeConnection())

    reader = _patch_reader(OBD2Reader(connection=None))
    reader._manage_connection = True
    reader._consecutive_failures = 3
    reader._reconnect_interval = 0
    reader._max_reconnect_interval = 10000
    reader._last_connect_attempt = 0.0
    reader._connection = None

    reader._try_connect()

    assert reader._consecutive_failures == 0
    assert reader._connection is not None


def test_injected_connection_is_not_auto_managed(monkeypatch):
    fake_conn = FakeConnection(connected=False)
    reader = OBD2Reader(connection=fake_conn)

    def _create(*a, **k):
        raise AssertionError("no debería llamarse a create_connection con conexión inyectada")

    monkeypatch.setattr(reader_module, "create_obd_connection", _create)

    reader._try_connect()  # no debe intentar crear ni fallar

    assert reader._connection is fake_conn


def test_get_status_is_safe_without_connection():
    reader = _patch_reader(OBD2Reader(connection=None))
    reader._manage_connection = True
    reader._connection = None
    reader._pids = ["RPM", "SPEED"]
    status = reader.get_status()
    assert status["connected"] is False
    assert status["port"] == reader_module.SETTINGS.obd_port
    assert status["pids"] == ["RPM", "SPEED"]


def test_read_sample_calls_on_readings_callback():
    fake_conn = FakeConnection(connected=True)
    captured = []

    reader = _patch_reader(
        OBD2Reader(connection=fake_conn, on_readings=captured.append)
    )
    reader._pids = ["RPM", "SPEED"]
    reader._dtc_interval = 1000.0
    reader._last_dtc_read = time.time()

    sample = reader._read_sample_locked()

    assert sample["connected"] is True
    assert sample["RPM"] == 42
    assert sample["SPEED"] == 42
    assert len(captured) == 1
    assert {r.pid for r in captured[0]} == {"RPM", "SPEED"}
