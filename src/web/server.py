"""Servidor web FastAPI para exponer datos OBD-II."""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.config import SETTINGS
from src.leds.controller import LEDController
from src.leds.scheduler import DayNightScheduler
from src.obd2.alerts import THRESHOLDS, evaluate
from src.obd2.reader import OBD2Reader
from src.storage.history import HistoryStore

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


class ColorPayload(BaseModel):
    r: int = Field(..., ge=0, le=255)
    g: int = Field(..., ge=0, le=255)
    b: int = Field(..., ge=0, le=255)


class BrightnessPayload(BaseModel):
    brightness: int = Field(..., ge=0, le=100)


class AutoModePayload(BaseModel):
    enabled: bool


def create_app(
    reader: OBD2Reader,
    led_controller: LEDController = None,
    history_store: Optional[HistoryStore] = None,
    led_scheduler: Optional[DayNightScheduler] = None,
) -> FastAPI:
    led_controller = led_controller or LEDController()

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        scheduler_task = None
        if led_scheduler is not None:
            scheduler_task = asyncio.create_task(led_scheduler.run())
        yield
        if scheduler_task is not None:
            led_scheduler.stop()
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass
        await led_controller.disconnect()

    app = FastAPI(title="Jarvis On Road", version="0.2.0", lifespan=_lifespan)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def root():
        return RedirectResponse(url="/static/index.html")

    @app.get("/favicon.ico")
    async def favicon():
        return Response(status_code=204)

    @app.get("/manifest.json")
    async def manifest():
        return FileResponse(
            STATIC_DIR / "manifest.json", media_type="application/manifest+json"
        )

    @app.get("/sw.js")
    async def service_worker():
        return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")

    @app.get("/api/health")
    async def health():
        alerts = evaluate(reader.get_latest())
        return {
            "status": "ok",
            "version": "0.2.0",
            "mock": SETTINGS.obd_mock,
            "alerts_level": alerts["level"],
        }

    @app.get("/api/obd/data")
    async def obd_data():
        return reader.get_latest()

    @app.get("/api/obd/status")
    async def obd_status():
        return reader.get_status()

    @app.get("/api/obd/dtcs")
    async def obd_dtcs():
        return reader.get_latest().get("dtcs", [])

    @app.get("/api/obd/alerts")
    async def obd_alerts():
        return evaluate(reader.get_latest())

    @app.get("/api/obd/recommendations")
    async def obd_recommendations():
        return [
            {
                "pid": config.pid,
                "label": config.label,
                "unit": config.unit,
                "min": config.min_value,
                "max": config.max_value,
            }
            for config in THRESHOLDS.values()
        ]

    def _require_history() -> HistoryStore:
        if history_store is None:
            raise HTTPException(
                status_code=503, detail="Histórico de datos OBD-II no disponible."
            )
        return history_store

    @app.get("/api/obd/history")
    async def obd_history(pid: str, hours: float = 1.0):
        """Lecturas en crudo de un PID en las últimas `hours` horas."""
        store = _require_history()
        since = time.time() - hours * 3600
        return store.get_readings(pid, since)

    @app.get("/api/obd/stats")
    async def obd_stats(pid: str, days: float = 7.0):
        """Estadísticas horarias (min/máx/media) de un PID en los últimos `days` días.

        Pensado para tendencias y análisis preventivo a medio/largo plazo,
        sin tener que escanear las lecturas en crudo.
        """
        store = _require_history()
        since = time.time() - days * 86400
        return store.get_hourly_stats(pid, since)

    @app.get("/api/obd/events")
    async def obd_events(days: float = 7.0, type: str | None = None):
        """Historial de eventos (alertas activadas/desactivadas, DTCs nuevos)."""
        store = _require_history()
        since = time.time() - days * 86400
        return store.get_events(since, event_type=type)

    @app.get("/api/leds/status")
    async def leds_status():
        status = dict(led_controller.status)
        if led_scheduler is not None:
            status["auto"] = led_scheduler.status
        return status

    @app.post("/api/leds/auto")
    async def leds_auto(payload: AutoModePayload = Body(...)):
        if led_scheduler is None:
            raise HTTPException(
                status_code=503, detail="Automatización día/noche de LEDs no disponible."
            )
        led_scheduler.set_auto_enabled(payload.enabled)
        return {"success": True, "state": led_scheduler.status}

    @app.post("/api/leds/on")
    async def leds_on():
        ok = await led_controller.turn_on()
        return {"success": ok, "state": led_controller.status}

    @app.post("/api/leds/off")
    async def leds_off():
        ok = await led_controller.turn_off()
        return {"success": ok, "state": led_controller.status}

    @app.post("/api/leds/color")
    async def leds_color(payload: ColorPayload = Body(...)):
        ok = await led_controller.set_color(payload.r, payload.g, payload.b)
        return {"success": ok, "state": led_controller.status}

    @app.post("/api/leds/brightness")
    async def leds_brightness(payload: BrightnessPayload = Body(...)):
        ok = await led_controller.set_brightness(payload.brightness)
        return {"success": ok, "state": led_controller.status}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        logger.info("Cliente WebSocket conectado.")
        try:
            while True:
                data = reader.get_latest()
                await websocket.send_text(json.dumps(data))
                await asyncio.sleep(SETTINGS.read_interval)
        except WebSocketDisconnect:
            logger.info("Cliente WebSocket desconectado.")
        except Exception:
            logger.exception("Error en WebSocket")
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    return app
