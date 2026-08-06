"""Evaluación de alertas a partir de los datos OBD-II.

Umbrales por defecto orientados a un Kia Ceed 2025 gasolina 1.0 T-GDI
(3 cilindros turbo, ~120 CV). Se pueden sobreescribir mediante variables
 de entorno o archivos de configuración en fases futuras.
"""

import os
from dataclasses import dataclass, replace
from typing import Any, Dict, List


@dataclass(frozen=True)
class ThresholdConfig:
    """Configuración de umbrales para un PID."""

    pid: str
    label: str
    unit: str
    min_value: float | None = None
    max_value: float | None = None
    warning_margin: float = 0.0
    critical_margin: float = 0.0
    message_low: str | None = None
    message_high: str | None = None


# Umbrales por defecto. Se pueden sobreescribir con variables de entorno
# mediante OBD_ALERT_<PID>_MAX, OBD_ALERT_<PID>_WARN, etc.
DEFAULT_THRESHOLDS: Dict[str, ThresholdConfig] = {
    "RPM": ThresholdConfig(
        pid="RPM",
        label="Revoluciones",
        unit="rpm",
        min_value=800,
        max_value=5000,
        warning_margin=500,
        critical_margin=1000,
        message_high="RPM altas para un 1.0 T-GDI; sube de marcha o reduce aceleración.",
    ),
    "SPEED": ThresholdConfig(
        pid="SPEED",
        label="Velocidad",
        unit="km/h",
        min_value=0,
        max_value=120,
        warning_margin=10,
        critical_margin=30,
        message_high="Exceso de velocidad. Ajusta la velocidad a los límites legales.",
    ),
    "COOLANT_TEMP": ThresholdConfig(
        pid="COOLANT_TEMP",
        label="Temp. refrigerante",
        unit="°C",
        min_value=80,
        max_value=105,
        warning_margin=5,
        critical_margin=13,
        message_low="Motor frío; evita altas cargas hasta que la aguja esté en su temperatura normal.",
        message_high="Temperatura del motor elevada; revisa refrigerante, ventilador y fugas.",
    ),
    "ENGINE_LOAD": ThresholdConfig(
        pid="ENGINE_LOAD",
        label="Carga del motor",
        unit="%",
        min_value=0,
        max_value=85,
        warning_margin=5,
        critical_margin=10,
        message_high="Carga del motor muy alta; si es constante, revisa averías o reduce ritmo.",
    ),
    "THROTTLE_POS": ThresholdConfig(
        pid="THROTTLE_POS",
        label="Acelerador",
        unit="%",
        min_value=0,
        max_value=100,
        warning_margin=0,
        critical_margin=0,
        message_high="Acelerador a fondo; conduce suave para ahorrar combustible y cuidar el motor.",
    ),
    "INTAKE_TEMP": ThresholdConfig(
        pid="INTAKE_TEMP",
        label="Temp. admisión",
        unit="°C",
        min_value=10,
        max_value=60,
        warning_margin=10,
        critical_margin=25,
        message_high="Temperatura de admisión alta; revisa intercooler o flujo de aire al turbo.",
    ),
}


def _load_thresholds() -> Dict[str, ThresholdConfig]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    for pid, config in thresholds.items():
        env_prefix = f"OBD_ALERT_{pid}"
        max_value = os.getenv(f"{env_prefix}_MAX")
        warn_margin = os.getenv(f"{env_prefix}_WARN")
        crit_margin = os.getenv(f"{env_prefix}_CRIT")
        overrides: Dict[str, float] = {}
        if max_value is not None:
            try:
                overrides["max_value"] = float(max_value)
            except ValueError:
                pass
        if warn_margin is not None:
            try:
                overrides["warning_margin"] = float(warn_margin)
            except ValueError:
                pass
        if crit_margin is not None:
            try:
                overrides["critical_margin"] = float(crit_margin)
            except ValueError:
                pass
        if overrides:
            thresholds[pid] = replace(config, **overrides)
    return thresholds


THRESHOLDS = _load_thresholds()


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Evalúa un diccionario de datos OBD-II y devuelve alertas."""
    alerts: List[Dict[str, Any]] = []
    pid_status: Dict[str, Dict[str, Any]] = {}
    global_level = "ok"

    for pid, raw_value in data.items():
        if pid in ("connected", "_last_update", "alerts"):
            continue
        threshold = THRESHOLDS.get(pid)
        value = _to_float(raw_value)
        if threshold is None or value is None:
            pid_status[pid] = {"level": "unknown", "message": None}
            continue

        status = _evaluate_pid(threshold, value)
        pid_status[pid] = status
        if status["level"] in ("warning", "critical"):
            alerts.append(
                {
                    "pid": pid,
                    "label": threshold.label,
                    "value": value,
                    "unit": threshold.unit,
                    "level": status["level"],
                    "message": status["message"],
                }
            )
        if status["level"] == "critical":
            global_level = "critical"
        elif status["level"] == "warning" and global_level == "ok":
            global_level = "warning"

    return {
        "level": global_level,
        "pids": pid_status,
        "alerts": alerts,
        "recommendations": _build_recommendations(),
    }


def _evaluate_pid(threshold: ThresholdConfig, value: float) -> Dict[str, Any]:
    level = "ok"
    message = None
    min_value = threshold.min_value
    max_value = threshold.max_value

    if min_value is not None and value < min_value:
        level = "warning"
        message = threshold.message_low or f"{threshold.label} por debajo del rango recomendado."
    if max_value is not None:
        warning_limit = max_value + threshold.warning_margin
        critical_limit = max_value + threshold.critical_margin
        if value > critical_limit:
            level = "critical"
            message = threshold.message_high or f"{threshold.label} críticamente alta."
        elif value > warning_limit and level == "ok":
            level = "warning"
            message = threshold.message_high or f"{threshold.label} por encima del rango recomendado."

    return {
        "level": level,
        "message": message,
        "recommended_min": min_value,
        "recommended_max": max_value,
    }


def _build_recommendations() -> List[Dict[str, Any]]:
    """Devuelve los rangos recomendados para cada PID conocido."""
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
