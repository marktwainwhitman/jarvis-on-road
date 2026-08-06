"""Tests para la reconexión automática del lector OBD-II."""

import src.obd2.reader as reader_module
from src.obd2.reader import OBD2Reader


class FakeConnection:
    def __init__(self, connected=True):
        self._connected = connected
        self.closed = False

    def is_connected(self):
        return self._connected

    def query(self, pid_name):
        return 42

    def close(self):
        self.closed = True

    def status(self):
        return {"connected": self._connected, "port": "FAKE", "pids": []}

    def get_dtcs(self):
        return []


def test_reader_without_connection_has_default_status():
    reader = OBD2Reader.__new__(OBD2Reader)  # evita __init__ para no tocar SETTINGS/threads
    reader._connection = None
    reader._pids = ["RPM"]
    status = reader.get_status()
    assert status["connected"] is False


def test_try_connect_creates_connection_on_success(monkeypatch):
    fake_conn = FakeConnection()
    monkeypatch.setattr(reader_module, "create_connection", lambda *a, **k: fake_conn)

    reader = OBD2Reader(connection=None)
    reader._manage_connection = True
    reader._reconnect_interval = 0  # sin límite de tasa para el test
    reader._last_connect_attempt = 0.0

    reader._try_connect()

    assert reader._connection is fake_conn


def test_try_connect_keeps_connection_none_on_failure(monkeypatch):
    def _raise(*a, **k):
        raise RuntimeError("adaptador no disponible")

    monkeypatch.setattr(reader_module, "create_connection", _raise)

    reader = OBD2Reader(connection=None)
    reader._manage_connection = True
    reader._reconnect_interval = 0
    reader._last_connect_attempt = 0.0

    reader._try_connect()

    assert reader._connection is None


def test_try_connect_respects_reconnect_interval(monkeypatch):
    calls = []

    def _create(*a, **k):
        calls.append(1)
        return FakeConnection()

    monkeypatch.setattr(reader_module, "create_connection", _create)

    reader = OBD2Reader(connection=None)
    reader._manage_connection = True
    reader._reconnect_interval = 1000  # muy largo, para forzar el rate-limit
    reader._last_connect_attempt = 0.0
    reader._connection = None

    reader._try_connect()
    reader._try_connect()

    assert len(calls) == 1


def test_injected_connection_is_not_auto_managed(monkeypatch):
    fake_conn = FakeConnection(connected=False)
    reader = OBD2Reader(connection=fake_conn)

    def _create(*a, **k):
        raise AssertionError("no debería llamarse a create_connection con conexión inyectada")

    monkeypatch.setattr(reader_module, "create_connection", _create)

    reader._try_connect()  # no debe intentar crear ni fallar

    assert reader._connection is fake_conn
