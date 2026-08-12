"""Tests para el collector autónomo OBD-II."""

import time
from pathlib import Path

from src.obd2.collector import OBDCollector, _on_readings
from src.obd2.connector import MockOBDConnection, PIDReading
from src.obd2.csv_logger import CSVLogger
from src.obd2.reader import OBD2Reader


def test_on_readings_writes_to_csv(tmp_path):
    logger = CSVLogger(tmp_path)
    readings = [
        PIDReading(
            pid="RPM", value=1500.0, unit="rpm", status="VALID", raw_value="M", ecu="TEST"
        )
    ]
    _on_readings(logger, readings)

    files = list(tmp_path.glob("*.csv"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8-sig")
    assert "RPM" in content
    assert "1500.0" in content


def test_collector_runs_and_writes_csv(tmp_path, monkeypatch):
    csv_logger = CSVLogger(tmp_path)
    mock_conn = MockOBDConnection(pids=["RPM", "SPEED"])
    reader = OBD2Reader(
        connection=mock_conn,
        on_readings=lambda readings: _on_readings(csv_logger, readings),
    )
    reader._interval = 0.05
    reader._dtc_interval = 3600.0

    collector = OBDCollector(reader, csv_logger)

    # Evitar que el test se cuelgue si algo falla.
    monkeypatch.setattr(
        collector, "run_forever", lambda: None
    )

    collector.start()
    time.sleep(0.2)
    collector.stop()

    files = list(tmp_path.glob("*.csv"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8-sig")
    assert "RPM" in content
    assert "SPEED" in content
