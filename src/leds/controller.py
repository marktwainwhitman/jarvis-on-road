"""Controlador BLE para tiras LED ELK-BLEDOM (Zengge)."""

import asyncio
import logging
from typing import Optional, Tuple

from src.config import SETTINGS

logger = logging.getLogger(__name__)

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"

CMD_ON = bytes.fromhex("7e040401000eef")
CMD_OFF = bytes.fromhex("7e040400000fef")

MAX_SEND_ATTEMPTS = 2


class LEDController:
    """Controla una tira LED BLE tipo ELK-BLEDOM usando Bleak.

    Mantiene una conexión BLE persistente para evitar el coste de
    reconectar en cada comando, y serializa los comandos con un lock
    porque un `BleakClient` no admite escrituras/conexiones concurrentes.
    """

    def __init__(self, mac_address: Optional[str] = None):
        self._mac = mac_address or SETTINGS.led_mac
        self._enabled = SETTINGS.led_enabled and bool(self._mac)
        self._state = {
            "on": False,
            "brightness": 100,
            "color": (255, 255, 255),
        }
        self._lock = asyncio.Lock()
        self._client = None  # BleakClient, creado de forma perezosa

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def status(self) -> dict:
        return {
            "enabled": self._enabled,
            "mac_address": self._mac,
            "on": self._state["on"],
            "brightness": self._state["brightness"],
            "color": list(self._state["color"]),
        }

    async def _get_client(self):
        from bleak import BleakClient

        if self._client is not None and self._client.is_connected:
            return self._client
        client = BleakClient(self._mac, timeout=10.0)
        await client.connect()
        self._client = client
        logger.info("Conectado por BLE a LEDs %s", self._mac)
        return client

    async def _reset_client(self) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                logger.exception("Error desconectando cliente BLE de LEDs")
            self._client = None

    async def disconnect(self) -> None:
        """Cierra la conexión BLE activa, si existe. Útil al apagar la app."""
        async with self._lock:
            await self._reset_client()

    async def _send(self, data: bytes) -> bool:
        if not self._enabled:
            logger.debug("LEDController deshabilitado; no se envía comando.")
            return False
        try:
            import bleak  # noqa: F401
        except ImportError:
            logger.error("Bleak no está instalado. No se pueden controlar LEDs.")
            return False

        async with self._lock:
            for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
                try:
                    client = await self._get_client()
                    await client.write_gatt_char(WRITE_CHAR_UUID, data, response=False)
                    logger.debug("Comando LED enviado: %s", data.hex())
                    return True
                except Exception:
                    logger.exception(
                        "Error enviando comando a LEDs %s (intento %s/%s)",
                        self._mac,
                        attempt,
                        MAX_SEND_ATTEMPTS,
                    )
                    await self._reset_client()
            return False

    async def turn_on(self) -> bool:
        ok = await self._send(CMD_ON)
        if ok:
            self._state["on"] = True
        return ok

    async def turn_off(self) -> bool:
        ok = await self._send(CMD_OFF)
        if ok:
            self._state["on"] = False
        return ok

    async def set_color(self, r: int, g: int, b: int) -> bool:
        ok = await self._send_color(r, g, b, self._state["brightness"])
        if ok:
            self._state["color"] = (r, g, b)
        return ok

    async def set_brightness(self, brightness: int) -> bool:
        brightness = max(0, min(brightness, 100))
        r, g, b = self._state["color"]
        ok = await self._send_color(r, g, b, brightness)
        if ok:
            self._state["brightness"] = brightness
        return ok

    async def _send_color(self, r: int, g: int, b: int, brightness: int) -> bool:
        rr, gg, bb = self._apply_brightness(r, g, b, brightness)
        data = bytes([0x7E, 0x07, 0x05, 0x03, rr, gg, bb, 0x00, 0xEF])
        return await self._send(data)

    @staticmethod
    def _apply_brightness(r: int, g: int, b: int, brightness: int) -> Tuple[int, int, int]:
        factor = brightness / 100.0
        return (
            max(0, min(255, int(r * factor))),
            max(0, min(255, int(g * factor))),
            max(0, min(255, int(b * factor))),
        )
