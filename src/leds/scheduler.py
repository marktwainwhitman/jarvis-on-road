"""Automatización día/noche de los LEDs (amanecer/atardecer calculado).

No depende de ningún sensor de luz ni PID de OBD-II (el coche no expone eso
por OBD-II estándar): calcula la salida y puesta de sol para una ubicación
aproximada mediante `astral`. Con un margen de error de ~30 minutos es
suficiente para esta zona, así que no hace falta GPS ni hardware adicional.

Se ejecuta como una tarea asíncrona dentro del mismo event loop de FastAPI
(no en un hilo aparte), porque `LEDController` usa un `asyncio.Lock` y sus
métodos son corutinas: mezclarlo con hilos y loops distintos daría problemas
de "Future atada a otro loop".
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun

from src.leds.controller import LEDController

logger = logging.getLogger(__name__)


class DayNightScheduler:
    """Enciende/apaga los LEDs automáticamente al anochecer/amanecer.

    El encendido se anticipa `pre_light_minutes` (por defecto 30) respecto al
    atardecer real, para que las luces ya estén encendidas cuando empieza a
    oscurecer en vez de esperar a la puesta de sol exacta. El apagado ocurre
    en el amanecer real.

    El modo automático se puede activar/desactivar en caliente (ver
    `set_auto_enabled`) sin perder el control manual de la PWA: cuando está
    desactivado, la tarea sigue viva pero no envía ningún comando.
    """

    def __init__(
        self,
        led_controller: LEDController,
        latitude: float,
        longitude: float,
        timezone: str = "Europe/Madrid",
        check_interval: float = 60.0,
        auto_enabled: bool = False,
        pre_light_minutes: float = 30.0,
    ):
        self._led_controller = led_controller
        self._location = LocationInfo(
            name="jarvis", region="", timezone=timezone, latitude=latitude, longitude=longitude
        )
        self._tzinfo = ZoneInfo(timezone)
        self._check_interval = check_interval
        self._auto_enabled = auto_enabled
        # Anticipa el encendido antes del atardecer real (p.ej. 30 min), para
        # que las luces ya estén encendidas cuando empieza a anochecer en vez
        # de esperar a la puesta de sol exacta. El apagado sigue ocurriendo en
        # el amanecer real.
        self._pre_light_delta = timedelta(minutes=pre_light_minutes)
        # None hasta el primer tick: fuerza una sincronización inicial del
        # estado de los LEDs en cuanto se activa el modo automático.
        self._last_is_night: Optional[bool] = None
        self._running = False

    # -- estado día/noche ---------------------------------------------------

    def _sun_times(self, now: Optional[datetime] = None) -> dict:
        now = now or datetime.now(self._tzinfo)
        return sun(self._location.observer, date=now.date(), tzinfo=self._tzinfo)

    def is_night(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(self._tzinfo)
        times = self._sun_times(now)
        light_on_time = times["sunset"] - self._pre_light_delta
        return now < times["sunrise"] or now >= light_on_time

    @property
    def auto_enabled(self) -> bool:
        return self._auto_enabled

    def set_auto_enabled(self, enabled: bool) -> None:
        self._auto_enabled = enabled
        if enabled:
            # Re-sincroniza el estado real de los LEDs con el sol la próxima
            # vez que se ejecute el ciclo, en vez de esperar al siguiente
            # amanecer/atardecer.
            self._last_is_night = None

    @property
    def status(self) -> dict:
        now = datetime.now(self._tzinfo)
        times = self._sun_times(now)
        return {
            "auto_enabled": self._auto_enabled,
            "is_night": self.is_night(now),
            "sunrise": times["sunrise"].isoformat(),
            "sunset": times["sunset"].isoformat(),
            "light_on_time": (times["sunset"] - self._pre_light_delta).isoformat(),
            "pre_light_minutes": self._pre_light_delta.total_seconds() / 60,
        }

    # -- ciclo de vida --------------------------------------------------------

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        """Tarea de fondo: revisa periódicamente si toca cambiar de estado.

        Pensada para lanzarse con `asyncio.create_task` desde el lifespan de
        FastAPI y cancelarse al apagar la app.
        """
        self._running = True
        try:
            while self._running:
                try:
                    await self._tick()
                except Exception:
                    logger.exception("Error en el ciclo de automatización de LEDs")
                await asyncio.sleep(self._check_interval)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False

    async def _tick(self) -> None:
        if not self._auto_enabled:
            return

        night = self.is_night()
        if night == self._last_is_night:
            return
        self._last_is_night = night

        if night:
            logger.info("Anocheciendo: encendiendo LEDs automáticamente.")
            await self._led_controller.turn_on()
        else:
            logger.info("Amaneciendo: apagando LEDs automáticamente.")
            await self._led_controller.turn_off()
