"""Módulo de conexión y lectura OBD-II."""

from .alerts import THRESHOLDS, ThresholdConfig, evaluate
from .connector import (
    BluetoothOBDConnection,
    MockOBDConnection,
    OBDConnection,
    PIDReading,
    create_connection,
    create_obd_connection,
)
from .pids import PID_REGISTRY, PIDDescriptor, get_pid_descriptor, pids_by_category
from .reader import OBD2Reader

__all__ = [
    "OBDConnection",
    "BluetoothOBDConnection",
    "MockOBDConnection",
    "PIDReading",
    "create_obd_connection",
    "create_connection",
    "OBD2Reader",
    "ThresholdConfig",
    "THRESHOLDS",
    "evaluate",
    "PID_REGISTRY",
    "PIDDescriptor",
    "get_pid_descriptor",
    "pids_by_category",
]
