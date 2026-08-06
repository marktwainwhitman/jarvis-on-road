"""Servidor web FastAPI para exponer datos OBD-II."""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.config import SETTINGS
from src.leds.controller import LEDController
from src.obd2.alerts import THRESHOLDS, evaluate
from src.obd2.reader import OBD2Reader

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


class ColorPayload(BaseModel):
    r: int = Field(..., ge=0, le=255)
    g: int = Field(..., ge=0, le=255)
    b: int = Field(..., ge=0, le=255)


class BrightnessPayload(BaseModel):
    brightness: int = Field(..., ge=0, le=100)


def create_app(reader: OBD2Reader, led_controller: LEDController = None) -> FastAPI:
    app = FastAPI(title="Jarvis On Road", version="0.2.0")
    led_controller = led_controller or LEDController()

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.on_event("shutdown")
    async def on_shutdown():
        await led_controller.disconnect()

    @app.get("/")
    async def root():
        return RedirectResponse(url="/static/index.html")

    @app.get("/favicon.ico")
    async def favicon():
        return Response(status_code=204)

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

    @app.get("/api/leds/status")
    async def leds_status():
        return led_controller.status

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
