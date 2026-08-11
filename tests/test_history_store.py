"""Tests para el histórico de datos OBD-II en SQLite (src/storage)."""

import time

import pytest

from src.storage.history import HOUR_SECONDS, HistoryStore


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "jarvis-test.db"
    s = HistoryStore(db_path=str(db_path), retention_days=30, flush_interval=1000.0)
    s.start()
    yield s
    s.stop()


def test_record_and_flush_persists_readings(store):
    store.record({"connected": True, "RPM": 2500, "SPEED": 80, "dtcs": []})
    store._flush()

    readings = store.get_readings("RPM", since_ts=0)
    assert len(readings) == 1
    assert readings[0]["value"] == 2500


def test_record_ignores_non_numeric_and_metadata_fields(store):
    store.record(
        {
            "connected": True,
            "_last_update": "2026-01-01T00:00:00Z",
            "RPM": None,
            "SPEED": 90,
            "dtcs": [],
        }
    )
    store._flush()

    assert store.get_readings("RPM", since_ts=0) == []
    assert len(store.get_readings("SPEED", since_ts=0)) == 1


def test_alert_transition_logs_single_event(store):
    # RPM por encima del umbral crítico (ver src/obd2/alerts.py) dispara alerta.
    store.record({"connected": True, "RPM": 7000, "dtcs": []})
    store.record({"connected": True, "RPM": 7000, "dtcs": []})  # sigue en critical, no debe duplicar
    store.record({"connected": True, "RPM": 1000, "dtcs": []})  # vuelve a ok
    store._flush()

    events = store.get_events(since_ts=0, event_type="alert")
    assert len(events) == 1
    assert events[0]["pid"] == "RPM"
    assert events[0]["level"] == "critical"


def test_new_dtc_logs_event_once(store):
    sample = {
        "connected": True,
        "dtcs": [{"code": "P0301", "description": "Fallo de encendido"}],
    }
    store.record(sample)
    store.record(sample)  # mismo código, no debe duplicar el evento
    store._flush()

    events = store.get_events(since_ts=0, event_type="dtc")
    assert len(events) == 1
    assert events[0]["code"] == "P0301"


def test_rollup_hour_aggregates_readings_into_hourly_stats(store):
    hour_ago = int(time.time()) - HOUR_SECONDS
    hour_bucket = hour_ago // HOUR_SECONDS

    with store._buffer_lock:
        store._buffer.extend(
            [
                (hour_ago, "RPM", 1000.0),
                (hour_ago + 10, "RPM", 2000.0),
                (hour_ago + 20, "RPM", 3000.0),
            ]
        )
    store._flush()

    store._rollup_hour(hour_bucket)

    stats = store.get_hourly_stats("RPM", since_ts=0)
    assert len(stats) == 1
    assert stats[0]["min"] == 1000.0
    assert stats[0]["max"] == 3000.0
    assert stats[0]["avg"] == 2000.0
    assert stats[0]["count"] == 3


def test_purge_old_readings_removes_rows_beyond_retention(tmp_path):
    db_path = tmp_path / "jarvis-purge.db"
    s = HistoryStore(db_path=str(db_path), retention_days=1, flush_interval=1000.0)
    s.start()
    try:
        old_ts = int(time.time()) - 2 * 24 * HOUR_SECONDS
        recent_ts = int(time.time())
        with s._buffer_lock:
            s._buffer.extend([(old_ts, "RPM", 1000.0), (recent_ts, "RPM", 2000.0)])
        s._flush()

        s._purge_old_readings()

        remaining = s.get_readings("RPM", since_ts=0)
        assert len(remaining) == 1
        assert remaining[0]["value"] == 2000.0
    finally:
        s.stop()
