"""Tests de integracion para los endpoints de FastAPI."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.obd2.reader import OBD2Reader
from src.web.server import create_app


@pytest.fixture
def mock_reader():
    reader = MagicMock(spec=OBD2Reader)
    reader.get_latest.return_value = {
        "connected": True,
        "_last_update": "2026-01-01T00:00:00Z",
        "RPM": 2500,
        "SPEED": 80,
        "dtcs": [],
    }
    reader.get_status.return_value = {
        "connected": True,
        "port": "MOCK",
        "pids": ["RPM", "SPEED"],
    }
    return reader


@pytest.fixture
def mock_led_controller():
    controller = MagicMock()
    controller.status = {
        "enabled": True,
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "on": False,
        "brightness": 100,
        "color": [255, 255, 255],
    }
    controller.turn_on = AsyncMock(return_value=True)
    controller.turn_off = AsyncMock(return_value=True)
    controller.set_color = AsyncMock(return_value=True)
    controller.set_brightness = AsyncMock(return_value=True)
    controller.disconnect = AsyncMock(return_value=None)
    return controller


@pytest.fixture
def mock_led_scheduler():
    scheduler = MagicMock()
    scheduler.status = {
        "auto_enabled": False,
        "is_night": False,
        "sunrise": "2026-01-01T08:00:00+01:00",
        "sunset": "2026-01-01T18:00:00+01:00",
    }
    scheduler.run = AsyncMock(return_value=None)
    return scheduler


@pytest.fixture
def client(mock_reader, mock_led_controller):
    app = create_app(mock_reader, mock_led_controller)
    with TestClient(app) as tc:
        yield tc


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "alerts_level" in data


def test_obd_data(client, mock_reader):
    res = client.get("/api/obd/data")
    assert res.status_code == 200
    assert res.json()["RPM"] == 2500
    mock_reader.get_latest.assert_called()


def test_obd_status(client, mock_reader):
    res = client.get("/api/obd/status")
    assert res.status_code == 200
    assert res.json()["connected"] is True
    mock_reader.get_status.assert_called()


def test_led_status(client):
    res = client.get("/api/leds/status")
    assert res.status_code == 200
    assert res.json()["enabled"] is True


def test_led_on(client, mock_led_controller):
    res = client.post("/api/leds/on")
    assert res.status_code == 200
    assert res.json()["success"] is True
    mock_led_controller.turn_on.assert_called_once()


def test_led_off(client, mock_led_controller):
    res = client.post("/api/leds/off")
    assert res.status_code == 200
    assert res.json()["success"] is True
    mock_led_controller.turn_off.assert_called_once()


def test_led_color_valid(client, mock_led_controller):
    res = client.post("/api/leds/color", json={"r": 10, "g": 20, "b": 30})
    assert res.status_code == 200
    assert res.json()["success"] is True
    mock_led_controller.set_color.assert_called_once_with(10, 20, 30)


def test_led_color_invalid_returns_422(client, mock_led_controller):
    res = client.post("/api/leds/color", json={"r": 300, "g": 0, "b": 0})
    assert res.status_code == 422
    mock_led_controller.set_color.assert_not_called()


def test_led_brightness_valid(client, mock_led_controller):
    res = client.post("/api/leds/brightness", json={"brightness": 50})
    assert res.status_code == 200
    assert res.json()["success"] is True
    mock_led_controller.set_brightness.assert_called_once_with(50)


def test_led_brightness_invalid_returns_422(client, mock_led_controller):
    res = client.post("/api/leds/brightness", json={"brightness": 150})
    assert res.status_code == 422
    mock_led_controller.set_brightness.assert_not_called()


def test_static_root_redirect(client):
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["location"] == "/static/index.html"


def test_manifest(client):
    res = client.get("/manifest.json")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Jarvis On Road"
    assert data["display"] == "standalone"


def test_service_worker(client):
    res = client.get("/sw.js")
    assert res.status_code == 200
    assert "addEventListener" in res.text


def test_index_html_is_served(client):
    res = client.get("/static/index.html")
    assert res.status_code == 200
    assert "Jarvis On Road" in res.text


def test_static_assets(client):
    for path in [
        "/static/css/main.css",
        "/static/js/app.js",
        "/static/manifest.json",
        "/static/icons/icon.svg",
    ]:
        res = client.get(path)
        assert res.status_code == 200, path


def test_obd_history_without_store_returns_503(client):
    res = client.get("/api/obd/history", params={"pid": "RPM"})
    assert res.status_code == 503


def test_obd_stats_without_store_returns_503(client):
    res = client.get("/api/obd/stats", params={"pid": "RPM"})
    assert res.status_code == 503


def test_obd_events_without_store_returns_503(client):
    res = client.get("/api/obd/events")
    assert res.status_code == 503


def test_obd_history_with_store(mock_reader, mock_led_controller):
    history_store = MagicMock()
    history_store.get_readings.return_value = [{"ts": 1, "value": 2500}]
    app = create_app(mock_reader, mock_led_controller, history_store)
    with TestClient(app) as client:
        res = client.get("/api/obd/history", params={"pid": "RPM", "hours": 2})
        assert res.status_code == 200
        assert res.json() == [{"ts": 1, "value": 2500}]
        history_store.get_readings.assert_called_once()
        assert history_store.get_readings.call_args.args[0] == "RPM"


def test_obd_stats_with_store(mock_reader, mock_led_controller):
    history_store = MagicMock()
    history_store.get_hourly_stats.return_value = [
        {"ts": 1, "min": 1, "max": 2, "avg": 1.5, "count": 2}
    ]
    app = create_app(mock_reader, mock_led_controller, history_store)
    with TestClient(app) as client:
        res = client.get("/api/obd/stats", params={"pid": "RPM", "days": 3})
        assert res.status_code == 200
        assert res.json()[0]["avg"] == 1.5


def test_obd_events_with_store(mock_reader, mock_led_controller):
    history_store = MagicMock()
    history_store.get_events.return_value = [
        {"ts": 1, "type": "alert", "pid": "RPM", "level": "critical", "code": None, "message": "x"}
    ]
    app = create_app(mock_reader, mock_led_controller, history_store)
    with TestClient(app) as client:
        res = client.get("/api/obd/events", params={"days": 1, "type": "alert"})
        assert res.status_code == 200
        assert res.json()[0]["type"] == "alert"
        history_store.get_events.assert_called_once()
        assert history_store.get_events.call_args.kwargs["event_type"] == "alert"


def test_leds_status_without_scheduler_has_no_auto_key(client):
    res = client.get("/api/leds/status")
    assert res.status_code == 200
    assert "auto" not in res.json()


def test_leds_auto_without_scheduler_returns_503(client):
    res = client.post("/api/leds/auto", json={"enabled": True})
    assert res.status_code == 503


def test_leds_status_includes_auto_state(mock_reader, mock_led_controller, mock_led_scheduler):
    app = create_app(mock_reader, mock_led_controller, None, mock_led_scheduler)
    with TestClient(app) as client:
        res = client.get("/api/leds/status")
        assert res.status_code == 200
        assert res.json()["auto"]["auto_enabled"] is False


def test_leds_auto_toggles_scheduler(mock_reader, mock_led_controller, mock_led_scheduler):
    app = create_app(mock_reader, mock_led_controller, None, mock_led_scheduler)
    with TestClient(app) as client:
        res = client.post("/api/leds/auto", json={"enabled": True})
        assert res.status_code == 200
        assert res.json()["success"] is True
        mock_led_scheduler.set_auto_enabled.assert_called_once_with(True)


def test_websocket_receives_data(client, mock_reader):
    mock_reader.get_latest.return_value = {
        "connected": True,
        "_last_update": "2026-01-01T00:00:00Z",
        "RPM": 1500,
        "dtcs": [],
    }
    with client.websocket_connect("/ws") as ws:
        data = ws.receive_json()
        assert data["RPM"] == 1500
