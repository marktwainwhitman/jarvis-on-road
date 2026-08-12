"""Tests para el controlador BLE de LEDs, usando un `bleak` simulado."""

import asyncio
import sys
import types

import pytest

from src.leds.controller import CMD_OFF, CMD_ON, WRITE_CHAR_UUID, LEDController


class FakeBleakClient:
    """Sustituto de `bleak.BleakClient` que registra las escrituras."""

    created_instances: list["FakeBleakClient"] = []
    fail_connect = False
    fail_write = False
    hang_write = False

    def __init__(self, mac_address, timeout=10.0):
        self.mac_address = mac_address
        self.timeout = timeout
        self.is_connected = False
        self.written = []
        FakeBleakClient.created_instances.append(self)

    async def connect(self):
        if FakeBleakClient.fail_connect:
            raise RuntimeError("fallo simulado de conexión BLE")
        self.is_connected = True

    async def disconnect(self):
        self.is_connected = False

    async def write_gatt_char(self, uuid, data, response=False):
        if FakeBleakClient.fail_write:
            raise RuntimeError("fallo simulado de escritura BLE")
        if FakeBleakClient.hang_write:
            await asyncio.sleep(10.0)
        self.written.append((uuid, data))


@pytest.fixture(autouse=True)
def fake_bleak(monkeypatch):
    FakeBleakClient.created_instances = []
    FakeBleakClient.fail_connect = False
    FakeBleakClient.fail_write = False
    FakeBleakClient.hang_write = False

    fake_module = types.ModuleType("bleak")
    fake_module.BleakClient = FakeBleakClient
    monkeypatch.setitem(sys.modules, "bleak", fake_module)
    yield FakeBleakClient


def make_controller() -> LEDController:
    controller = LEDController(mac_address="AA:BB:CC:DD:EE:FF")
    controller._enabled = True  # evita depender de SETTINGS globales en el test
    return controller


@pytest.mark.asyncio
async def test_disabled_controller_does_not_send_and_keeps_state():
    controller = LEDController(mac_address="AA:BB:CC:DD:EE:FF")
    controller._enabled = False

    ok = await controller.turn_on()

    assert ok is False
    assert controller.status["on"] is False
    assert FakeBleakClient.created_instances == []


@pytest.mark.asyncio
async def test_turn_on_success_updates_state_and_sends_expected_bytes():
    controller = make_controller()

    ok = await controller.turn_on()

    assert ok is True
    assert controller.status["on"] is True
    client = FakeBleakClient.created_instances[0]
    assert client.written == [(WRITE_CHAR_UUID, bytes.fromhex("7e0404f00001ff00ef"))]


@pytest.mark.asyncio
async def test_turn_off_sends_expected_bytes():
    controller = make_controller()

    ok = await controller.turn_off()

    assert ok is True
    assert controller.status["on"] is False
    client = FakeBleakClient.created_instances[0]
    assert client.written == [(WRITE_CHAR_UUID, CMD_OFF)]


@pytest.mark.asyncio
async def test_failed_write_does_not_update_state(fake_bleak):
    controller = make_controller()
    fake_bleak.fail_write = True

    ok = await controller.turn_on()

    assert ok is False
    assert controller.status["on"] is False


@pytest.mark.asyncio
async def test_connection_is_reused_across_commands():
    controller = make_controller()

    await controller.turn_on()
    await controller.set_color(10, 20, 30)

    # Un único cliente BLE creado y reutilizado para ambos comandos.
    assert len(FakeBleakClient.created_instances) == 1
    client = FakeBleakClient.created_instances[0]
    assert len(client.written) == 2


@pytest.mark.asyncio
async def test_reconnects_after_failed_command():
    controller = make_controller()
    await controller.turn_on()
    first_client = FakeBleakClient.created_instances[0]

    # Simula que la conexión se cae entre comandos.
    first_client.is_connected = False

    await controller.turn_off()

    assert len(FakeBleakClient.created_instances) == 2


@pytest.mark.asyncio
async def test_set_color_applies_current_brightness():
    controller = make_controller()
    await controller.set_brightness(50)

    await controller.set_color(200, 100, 40)

    client = FakeBleakClient.created_instances[-1]
    _, data = client.written[-1]
    # 50% de brillo sobre (200, 100, 40) -> (100, 50, 20)
    assert data == bytes([0x7E, 0x07, 0x05, 0x03, 100, 50, 20, 0x00, 0xEF])
    assert controller.status["color"] == [200, 100, 40]
    assert controller.status["brightness"] == 50


@pytest.mark.asyncio
async def test_commands_are_serialized_with_lock():
    controller = make_controller()

    results = await asyncio.gather(
        controller.turn_on(),
        controller.set_color(1, 2, 3),
        controller.set_brightness(80),
    )

    assert all(results)
    # Solo debería haberse creado un cliente puesto que el lock serializa
    # las conexiones y la conexión se mantiene abierta entre comandos.
    assert len(FakeBleakClient.created_instances) == 1


@pytest.mark.asyncio
async def test_hanging_write_is_aborted_and_does_not_deadlock(fake_bleak):
    controller = make_controller()
    controller._ble_timeout = 0.1  # timeout muy corto para el test
    fake_bleak.hang_write = True

    # El primer comando debería fallar por timeout, no quedarse colgado.
    ok = await controller.turn_on()
    assert ok is False
    assert controller.status["on"] is False

    # Tras el timeout, el lock se ha liberado: un comando posterior funciona.
    fake_bleak.hang_write = False
    ok = await controller.turn_on()
    assert ok is True
    assert controller.status["on"] is True
