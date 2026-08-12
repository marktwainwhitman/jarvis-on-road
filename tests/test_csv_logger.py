"""Tests para el registro de lecturas OBD-II en CSV."""

import csv
from datetime import datetime, timezone

import pytest

from src.obd2.connector import PIDReading
from src.obd2.csv_logger import CSVLogger, FIELDNAMES


@pytest.fixture
def logger(tmp_path):
    return CSVLogger(tmp_path)


def _reading(
    pid="RPM",
    value=1000.0,
    status="VALID",
    unit="rpm",
    raw="MOCK:RPM",
    ecu="MOCK",
):
    return PIDReading(
        pid=pid,
        value=value,
        unit=unit,
        status=status,
        raw_value=raw,
        ecu=ecu,
    )


def test_write_creates_daily_csv_file(logger, tmp_path):
    now = datetime.now(timezone.utc)
    logger.write([_reading()])
    expected = tmp_path / f"{now.date().isoformat()}.csv"
    assert expected.exists()


def test_csv_contains_header(logger, tmp_path):
    logger.write([_reading()])
    expected = tmp_path / f"{datetime.now(timezone.utc).date().isoformat()}.csv"
    with expected.open("r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
    assert header == FIELDNAMES


def test_csv_row_values(logger):
    logger.write([_reading(pid="SPEED", value=0.0, status="ZERO", unit="km/h")])
    path = logger._current_path
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["pid"] == "SPEED"
    assert rows[0]["value"] == "0.0"
    assert rows[0]["status"] == "ZERO"
    assert rows[0]["unit"] == "km/h"


def test_unavailable_value_is_empty_string(logger):
    logger.write(
        [PIDReading(pid="MAF", value=None, unit="g/s", status="UNAVAILABLE", raw_value=None, ecu="")]
    )
    path = logger._current_path
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert rows[0]["value"] == ""
    assert rows[0]["status"] == "UNAVAILABLE"


def test_multiple_readings_in_same_row_call(logger):
    logger.write(
        [
            _reading(pid="RPM", value=1000.0),
            _reading(pid="SPEED", value=0.0, status="ZERO", unit="km/h"),
        ]
    )
    path = logger._current_path
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 2


def test_rotates_to_new_file_on_next_day(logger, tmp_path, monkeypatch):
    from datetime import date

    first_date = date(2026, 8, 12)
    second_date = date(2026, 8, 13)

    class FakeDate:
        calls = 0

        @classmethod
        def now(cls, tz=None):
            cls.calls += 1
            if cls.calls == 1:
                return datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)
            return datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc)

    monkeypatch.setattr("src.obd2.csv_logger.datetime", FakeDate)

    logger.write([_reading()])
    first_path = logger._current_path
    assert first_path.name == f"{first_date.isoformat()}.csv"

    logger.write([_reading()])
    second_path = logger._current_path
    assert second_path.name == f"{second_date.isoformat()}.csv"
    assert second_path.exists()


def test_context_manager_closes_file(logger):
    with logger:
        logger.write([_reading()])
    assert logger._current_file is None
