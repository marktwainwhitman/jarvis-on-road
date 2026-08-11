"""Tests para la automatización día/noche de LEDs (src/leds/scheduler.py)."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from src.leds.scheduler import DayNightScheduler

# Ubicación aproximada de la zona Huelva-Sevilla-Cádiz.
LAT, LON, TZ = 37.2, -6.4, "Europe/Madrid"


def make_scheduler(auto_enabled: bool = True, pre_light_minutes: float = 30.0) -> DayNightScheduler:
    controller = AsyncMock()
    return DayNightScheduler(
        controller,
        latitude=LAT,
        longitude=LON,
        timezone=TZ,
        check_interval=0.01,
        auto_enabled=auto_enabled,
        pre_light_minutes=pre_light_minutes,
    ), controller


def test_is_night_at_midday_is_false():
    scheduler, _ = make_scheduler()
    noon = datetime(2026, 6, 21, 13, 0, tzinfo=ZoneInfo(TZ))
    assert scheduler.is_night(noon) is False


def test_is_night_at_midnight_is_true():
    scheduler, _ = make_scheduler()
    midnight = datetime(2026, 6, 21, 2, 0, tzinfo=ZoneInfo(TZ))
    assert scheduler.is_night(midnight) is True


def test_status_reports_sunrise_and_sunset():
    scheduler, _ = make_scheduler()
    status = scheduler.status
    assert "sunrise" in status
    assert "sunset" in status
    assert status["auto_enabled"] is True


def test_status_reports_light_on_time_before_sunset():
    scheduler, _ = make_scheduler(pre_light_minutes=30)
    status = scheduler.status
    sunset = datetime.fromisoformat(status["sunset"])
    light_on = datetime.fromisoformat(status["light_on_time"])
    assert (sunset - light_on).total_seconds() == pytest.approx(30 * 60)
    assert status["pre_light_minutes"] == pytest.approx(30.0)


def test_is_night_true_before_sunset_within_pre_light_window():
    scheduler, _ = make_scheduler(pre_light_minutes=30)
    now = datetime.now(ZoneInfo(TZ))
    times = scheduler._sun_times(now)
    just_before_sunset = times["sunset"] - timedelta(minutes=10)
    assert scheduler.is_night(just_before_sunset) is True


def test_is_night_false_well_before_sunset():
    scheduler, _ = make_scheduler(pre_light_minutes=30)
    now = datetime.now(ZoneInfo(TZ))
    times = scheduler._sun_times(now)
    well_before_sunset = times["sunset"] - timedelta(minutes=60)
    assert scheduler.is_night(well_before_sunset) is False


@pytest.mark.asyncio
async def test_tick_turns_on_when_disabled():
    scheduler, controller = make_scheduler(auto_enabled=False)

    await scheduler._tick()

    controller.turn_on.assert_not_called()
    controller.turn_off.assert_not_called()


@pytest.mark.asyncio
async def test_tick_syncs_state_on_first_run_at_night():
    scheduler, controller = make_scheduler(auto_enabled=True)
    scheduler.is_night = lambda now=None: True  # forzamos "de noche"

    await scheduler._tick()

    controller.turn_on.assert_called_once()
    controller.turn_off.assert_not_called()


@pytest.mark.asyncio
async def test_tick_syncs_state_on_first_run_at_day():
    scheduler, controller = make_scheduler(auto_enabled=True)
    scheduler.is_night = lambda now=None: False  # forzamos "de día"

    await scheduler._tick()

    controller.turn_off.assert_called_once()
    controller.turn_on.assert_not_called()


@pytest.mark.asyncio
async def test_tick_only_acts_on_transitions():
    scheduler, controller = make_scheduler(auto_enabled=True)
    scheduler.is_night = lambda now=None: True

    await scheduler._tick()  # noche -> enciende
    await scheduler._tick()  # sigue de noche -> no debe repetir

    controller.turn_on.assert_called_once()


@pytest.mark.asyncio
async def test_set_auto_enabled_resyncs_on_next_tick():
    scheduler, controller = make_scheduler(auto_enabled=True)
    scheduler.is_night = lambda now=None: True
    await scheduler._tick()  # enciende y fija _last_is_night=True
    controller.turn_on.reset_mock()

    scheduler.set_auto_enabled(False)
    scheduler.set_auto_enabled(True)  # debe forzar re-sincronización
    await scheduler._tick()

    controller.turn_on.assert_called_once()
