"""Controlador BLE para tiras LED ELK-BLEDOM (Zengge)."""

import asyncio
import logging
from typing import Callable, Optional, Tuple

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

    Todas las operaciones BLE tienen un timeout configurable para evitar
    que un dispositivo desconectado/saturado deje bloqueado el controlador.
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
        self._ble_timeout = SETTINGS.led_ble_timeout

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
        client = BleakClient(self._mac, timeout=self._ble_timeout)
        await client.connect()
        self._client = client
        logger.info("Conectado por BLE a LEDs %s", self._mac)
        return client

    async def _reset_client(self) -> None:
        if self._client is not None:
            try:
                await asyncio.wait_for(
                    self._client.disconnect(), timeout=self._ble_timeout
                )
            except Exception:
                logger.exception("Error desconectando cliente BLE de LEDs")
            self._client = None

    async def disconnect(self) -> None:
        """Cierra la conexión BLE activa, si existe. Útil al apagar la app."""
        async with self._lock:
            await self._reset_client()

    async def _send_locked(self, data: bytes) -> bool:
        """Envia `data` por BLE asumiendo que el lock ya esta tomado.

        Protege con timeout tanto la conexion como la escritura GATT para
        evitar bloqueos permanentes del controlador.
        """
        try:
            import bleak  # noqa: F401
        except ImportError:
            logger.error("Bleak no está instalado. No se pueden controlar LEDs.")
            return False

        for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
            try:
                client = await asyncio.wait_for(
                    self._get_client(), timeout=self._ble_timeout
                )
                await asyncio.wait_for(
                    client.write_gatt_char(WRITE_CHAR_UUID, data, response=False),
                    timeout=self._ble_timeout,
                )
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

    async def _send_cmd(
        self,
        data_builder: Callable[[], bytes],
        on_success: Optional[Callable[[], None]] = None,
    ) -> bool:
        """Serializa el comando, construye el payload bajo lock y actualiza
        el estado solo si el envio tuvo exito.

        Asi evitamos lecturas/escrituras concurrentes de `_state` y aseguramos
        que el payload enviado se corresponda exactamente con el estado
        aplicado.
        """
        if not self._enabled:
            logger.debug("LEDController deshabilitado; no se envía comando.")
            return False

        async with self._lock:
            data = data_builder()
            ok = await self._send_locked(data)
            if ok and on_success is not None:
                on_success()
        return ok

    async def turn_on(self) -> bool:
        return await self._send_cmd(lambda: CMD_ON, lambda: self._state.__setitem__("on", True))

    async def turn_off(self) -> bool:
        return await self._send_cmd(lambda: CMD_OFF, lambda: self._state.__setitem__("on", False))

    async def set_color(self, r: int, g: int, b: int) -> bool:
        def build():
            brightness = self._state["brightness"]
            rr, gg, bb = self._apply_brightness(r, g, b, brightness)
            return bytes([0x7E, 0x07, 0x05, 0x03, rr, gg, bb, 0x00, 0xEF])

        def apply():
            self._state["color"] = (r, g, b)

        return await self._send_cmd(build, apply)

    async def set_brightness(self, brightness: int) -> bool:
        brightness = max(0, min(brightness, 100))

        def build():
            r, g, b = self._state["color"]
            rr, gg, bb = self._apply_brightness(r, g, b, brightness)
            return bytes([0x7E, 0x07, 0x05, 0x03, rr, gg, bb, 0x00, 0xEF])

        def apply():
            self._state["brightness"] = brightness

        return await self._send_cmd(build, apply)

    @staticmethod
    def _apply_brightness(r: int, g: int, b: int, brightness: int) -> Tuple[int, int, int]:
        factor = brightness / 100.0
        return (
            max(0, min(255, int(r * factor))),
            max(0, min(255, int(g * factor))),
            max(0, min(255, int(b * factor))),
        )
