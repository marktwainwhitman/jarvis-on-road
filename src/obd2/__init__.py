"""Módulo de conexión y lectura OBD-II."""

from .alerts import THRESHOLDS, ThresholdConfig, evaluate
from .connector import OBD2Connection, OBD2MockConnection, create_connection
from .reader import OBD2Reader

__all__ = [
    "OBD2Connection",
    "OBD2MockConnection",
    "create_connection",
    "OBD2Reader",
    "ThresholdConfig",
    "THRESHOLDS",
    "evaluate",
]
