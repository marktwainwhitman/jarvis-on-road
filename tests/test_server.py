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
