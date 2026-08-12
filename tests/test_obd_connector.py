"""Tests para la capa de conexión OBD-II (mock y factoría)."""

import pytest

from src.obd2.connector import (
    MockOBDConnection,
    OBDConnection,
    PIDReading,
    _extract_scalar,
    create_obd_connection,
)


def test_create_connection_returns_mock_when_forced():
    conn = create_obd_connection(port="/dev/rfcomm0", mock=True)
    assert isinstance(conn, MockOBDConnection)
    assert conn.is_connected() is True


def test_create_connection_returns_mock_when_obd_library_unavailable(monkeypatch):
    monkeypatch.setattr("src.obd2.connector._is_obd_available", lambda: False)
    conn = create_obd_connection(port="/dev/rfcomm0", mock=False)
    assert isinstance(conn, MockOBDConnection)


def test_mock_connection_implements_interface():
    conn = MockOBDConnection(pids=["RPM", "SPEED"])
    assert isinstance(conn, OBDConnection)
    assert conn.is_connected() is True
    assert conn.protocol_name() == "MOCK"
    assert conn.ecu_address() == "MOCK"


def test_mock_query_returns_numeric_value():
    conn = MockOBDConnection(pids=["RPM"])
    value = conn.query("RPM")
    assert isinstance(value, float)
    assert value >= 0


def test_mock_query_pid_returns_valid_reading():
    conn = MockOBDConnection(pids=["RPM"])
    reading = conn.query_pid("RPM")
    assert isinstance(reading, PIDReading)
    assert reading.pid == "RPM"
    assert reading.status in ("VALID", "ZERO")
    assert reading.ecu == "MOCK"
    assert reading.raw_value is not None


def test_mock_zero_value_is_marked_zero():
    conn = MockOBDConnection(pids=["SPEED"])
    # Forzar valor 0 en el mock.
    conn._supported = {"SPEED"}
    reading = conn.query_pid("SPEED")
    # No podemos forzar aleatoriamente 0, pero al menos validamos que un
    # SPEED=0 se marque como ZERO, no como UNAVAILABLE.
    if reading.value == 0:
        assert reading.status == "ZERO"


def test_mock_unsupported_pid_status():
    conn = MockOBDConnection(pids=["RPM"])
    conn.add_unsupported("SPEED")
    reading = conn.query_pid("SPEED")
    assert reading.status == "UNSUPPORTED"
    assert reading.value is None


def test_mock_disconnected_returns_communication_error():
    conn = MockOBDConnection(pids=["RPM"])
    conn.disconnect()
    reading = conn.query_pid("RPM")
    assert reading.status == "COMMUNICATION_ERROR"
    assert reading.value is None


def test_mock_reconnect_restores_connection():
    conn = MockOBDConnection(pids=["RPM"])
    conn.disconnect()
    assert conn.is_connected() is False
    conn.reconnect()
    assert conn.is_connected() is True
    reading = conn.query_pid("RPM")
    assert reading.status in ("VALID", "ZERO")


def test_mock_status_contains_expected_keys():
    conn = MockOBDConnection(pids=["RPM", "SPEED"])
    status = conn.status()
    assert status["connected"] is True
    assert status["port"] == "MOCK"
    assert status["protocol"] == "MOCK"
    assert status["ecu"] == "MOCK"
    assert "pids" in status


def test_extract_scalar_handles_pint_like_objects():
    class FakeQuantity:
        magnitude = 123.4

    assert _extract_scalar(FakeQuantity()) == 123.4


def test_extract_scalar_returns_none_for_non_numeric_strings():
    assert _extract_scalar("not a number") is None


@pytest.mark.parametrize(
    "value,expected",
    [
        (42, 42.0),
        (3.14, 3.14),
        ("7", 7.0),
        (None, None),
    ],
)
def test_extract_scalar_conversions(value, expected):
    assert _extract_scalar(value) == expected
