"""Catálogo de PIDs OBD-II estándar usados por Jarvis On Road.

Los nombres de comando (``command_name``) se resuelven en tiempo de ejecución
contra ``obd.commands`` cuando está disponible la librería ``python-obd``. Si
no está disponible (modo mock o desarrollo sin dependencias), se usan las
propiedades definidas aquí para generar lecturas simuladas.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class PIDDescriptor:
    """Metadatos de un PID OBD-II."""

    command_name: str  # Nombre en obd.commands, p. ej. "RPM"
    label: str  # Nombre legible para humanos
    unit: str  # Unidad de medida
    pid_hex: Optional[str] = None  # Identificador hexadecimal del PID (sin modo)
    category: str = "generic"  # "high", "medium", "diagnostic"...


PID_REGISTRY: Dict[str, PIDDescriptor] = {
    # Alta prioridad
    "RPM": PIDDescriptor("RPM", "Engine RPM", "rpm", pid_hex="0C", category="high"),
    "SPEED": PIDDescriptor("SPEED", "Vehicle Speed", "km/h", pid_hex="0D", category="high"),
    "ENGINE_LOAD": PIDDescriptor(
        "ENGINE_LOAD", "Engine Load", "%", pid_hex="04", category="high"
    ),
    "COOLANT_TEMP": PIDDescriptor(
        "COOLANT_TEMP", "Coolant Temperature", "°C", pid_hex="05", category="high"
    ),
    "INTAKE_TEMP": PIDDescriptor(
        "INTAKE_TEMP", "Intake Air Temperature", "°C", pid_hex="0F", category="high"
    ),
    "MAF": PIDDescriptor("MAF", "Mass Air Flow Rate", "g/s", pid_hex="10", category="high"),
    "INTAKE_PRESSURE": PIDDescriptor(
        "INTAKE_PRESSURE", "Intake Manifold Pressure", "kPa", pid_hex="0B", category="high"
    ),
    "SHORT_FUEL_TRIM_1": PIDDescriptor(
        "SHORT_FUEL_TRIM_1", "Short Term Fuel Trim Bank 1", "%", pid_hex="06", category="high"
    ),
    "LONG_FUEL_TRIM_1": PIDDescriptor(
        "LONG_FUEL_TRIM_1", "Long Term Fuel Trim Bank 1", "%", pid_hex="07", category="high"
    ),
    "FUEL_PRESSURE": PIDDescriptor(
        "FUEL_PRESSURE", "Fuel Pressure", "kPa", pid_hex="0A", category="high"
    ),
    "CONTROL_MODULE_VOLTAGE": PIDDescriptor(
        "CONTROL_MODULE_VOLTAGE", "Control Module Voltage", "V", pid_hex="42", category="high"
    ),
    # Prioridad media
    "THROTTLE_POS": PIDDescriptor(
        "THROTTLE_POS", "Throttle Position", "%", pid_hex="11", category="medium"
    ),
    "TIMING_ADVANCE": PIDDescriptor(
        "TIMING_ADVANCE", "Timing Advance", "°", pid_hex="0E", category="medium"
    ),
    "EGR_ERROR": PIDDescriptor("EGR_ERROR", "EGR Error", "%", pid_hex="2D", category="medium"),
    "RUN_TIME": PIDDescriptor(
        "RUN_TIME", "Engine Run Time", "s", pid_hex="1F", category="medium"
    ),
    "FUEL_LEVEL": PIDDescriptor(
        "FUEL_LEVEL", "Fuel Level Input", "%", pid_hex="2F", category="medium"
    ),
    "O2_B1S1": PIDDescriptor(
        "O2_B1S1", "O2 Bank 1 Sensor 1 Voltage", "V", pid_hex="14", category="medium"
    ),
    "O2_B1S2": PIDDescriptor(
        "O2_B1S2", "O2 Bank 1 Sensor 2 Voltage", "V", pid_hex="15", category="medium"
    ),
    # Diagnóstico / monitor
    "STATUS": PIDDescriptor(
        "STATUS", "OBD Monitor Status", "", pid_hex="01", category="diagnostic"
    ),
}


def get_pid_descriptor(name: str) -> Optional[PIDDescriptor]:
    """Devuelve el descriptor de un PID por su nombre."""
    return PID_REGISTRY.get(name)


def pids_by_category(category: str) -> Dict[str, PIDDescriptor]:
    """Devuelve los PIDs de una categoría dada."""
    return {name: desc for name, desc in PID_REGISTRY.items() if desc.category == category}
