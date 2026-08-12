"""Tests para la herramienta de descubrimiento OBD-II."""

from src.obd2.connector import MockOBDConnection, PIDReading
from src.obd2.discovery import discover


class VerboseMockConnection(MockOBDConnection):
    def query_pid(self, pid_name: str) -> PIDReading:
        # Devuelve siempre un valor fijo para poder validar la salida.
        return PIDReading(
            pid=pid_name,
            value=1234.0 if pid_name == "RPM" else 0.0,
            unit="rpm" if pid_name == "RPM" else "",
            status="VALID" if pid_name == "RPM" else "ZERO",
            raw_value=f"TEST:{pid_name}",
            ecu="TEST",
        )


def test_discovery_prints_header_and_pid_rows(capsys):
    conn = VerboseMockConnection(pids=["RPM", "SPEED"])
    discover(conn, pids=["RPM", "SPEED"])
    captured = capsys.readouterr().out
    assert "Conectado" in captured
    assert "RPM" in captured
    assert "SPEED" in captured
    assert "VALID" in captured
    assert "ZERO" in captured
