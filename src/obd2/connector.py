"""Conectores OBD-II: real (python-obd vía Bluetooth) y simulado (mock)."""

import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.obd2.pids import PID_REGISTRY, get_pid_descriptor

logger = logging.getLogger(__name__)


def _is_obd_available() -> bool:
    try:
        import obd  # noqa: F401
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class PIDReading:
    """Lectura enriquecida de un PID OBD-II."""

    pid: str
    value: Optional[float]
    unit: Optional[str]
    status: str  # VALID, ZERO, UNAVAILABLE, UNSUPPORTED, COMMUNICATION_ERROR
    raw_value: Optional[str]
    ecu: Optional[str]

    def is_valid(self) -> bool:
        return self.status in ("VALID", "ZERO")


class OBDConnection(ABC):
    """Interfaz común para conexiones OBD-II."""

    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @abstractmethod
    def query(self, pid_name: str) -> Optional[Any]:
        """Devuelve solo el valor escalar del PID (compatibilidad heredada)."""
        ...

    @abstractmethod
    def query_pid(self, pid_name: str) -> PIDReading:
        """Devuelve una lectura con metadatos, estado y valor raw."""
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    @abstractmethod
    def status(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_dtcs(self) -> List[Tuple[str, Optional[str]]]:
        ...

    @abstractmethod
    def protocol_name(self) -> Optional[str]:
        ...

    @abstractmethod
    def ecu_address(self) -> Optional[str]:
        ...


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------


class MockOBDConnection(OBDConnection):
    """Conexión simulada que genera valores realistas pero identificados como mock."""

    def __init__(self, pids: Optional[List[str]] = None):
        self._pids = pids or list(PID_REGISTRY.keys())
        self._supported = set(self._pids)
        self._connected = True
        self._protocol = "MOCK"
        self._ecu = "MOCK"
        self._start_time = time.time()

    # --- utilidades para tests ------------------------------------------------

    def disconnect(self) -> None:
        self._connected = False

    def reconnect(self) -> None:
        self._connected = True

    def set_supported(self, pids: List[str]) -> None:
        self._supported = set(pids)

    def add_unsupported(self, pid: str) -> None:
        self._supported.discard(pid)

    # --- interfaz pública -----------------------------------------------------

    def is_connected(self) -> bool:
        return self._connected

    def protocol_name(self) -> Optional[str]:
        return self._protocol

    def ecu_address(self) -> Optional[str]:
        return self._ecu

    def query(self, pid_name: str) -> Optional[Any]:
        return self.query_pid(pid_name).value

    def query_pid(self, pid_name: str) -> PIDReading:
        descriptor = get_pid_descriptor(pid_name)
        if not self._connected:
            return _error_reading(pid_name, descriptor, "COMMUNICATION_ERROR")
        if pid_name not in self._supported:
            return _error_reading(pid_name, descriptor, "UNSUPPORTED")

        raw, value = _generate_mock_reading(pid_name)
        status = "ZERO" if value == 0 else "VALID"
        return PIDReading(
            pid=pid_name,
            value=value,
            unit=descriptor.unit if descriptor else None,
            status=status,
            raw_value=raw,
            ecu=self._ecu,
        )

    def close(self) -> None:
        self._connected = False

    def status(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "port": "MOCK",
            "protocol": self._protocol,
            "ecu": self._ecu,
            "pids": self._pids,
            "elapsed_seconds": round(time.time() - self._start_time, 1),
        }

    def get_dtcs(self) -> List[Tuple[str, Optional[str]]]:
        # En modo simulado devuelve ocasionalmente un DTC de ejemplo.
        if random.random() < 0.15:
            return [("P0301", "Fallo de encendido cilindro 1 (simulado)")]
        return []


# ---------------------------------------------------------------------------
# Real (Bluetooth / python-obd)
# ---------------------------------------------------------------------------


class BluetoothOBDConnection(OBDConnection):
    """Conexión real a un adaptador ELM327 compatible vía puerto serie."""

    def __init__(
        self,
        port: str,
        pids: Optional[List[str]] = None,
        protocol: Optional[str] = None,
        timeout: float = 30,
        fast: bool = False,
        check_voltage: bool = True,
        start_low_power: bool = False,
        baudrate: Optional[int] = None,
    ):
        import obd

        self._port = port
        self._protocol_arg = protocol
        self._pids = pids or list(PID_REGISTRY.keys())
        self._commands = self._resolve_commands(obd, self._pids)
        self._ecu_address: Optional[str] = None
        self._protocol_name: Optional[str] = None
        self._protocol_id: Optional[str] = None

        obd_kwargs: Dict[str, Any] = {
            "timeout": timeout,
            "fast": fast,
            "check_voltage": check_voltage,
            "start_low_power": start_low_power,
        }
        if protocol:
            obd_kwargs["protocol"] = protocol
        if baudrate is not None:
            obd_kwargs["baudrate"] = baudrate

        logger.info("Conectando a OBD-II en %s (protocol=%s, fast=%s)...", port, protocol, fast)
        self._connection = obd.OBD(port, **obd_kwargs)
        logger.info("Estado de conexión OBD-II: %s", self._connection.status())

        try:
            self._protocol_name = self._connection.protocol_name() or None
            self._protocol_id = self._connection.protocol_id() or None
        except Exception:
            logger.exception("No se pudo obtener el protocolo detectado")

    def _resolve_commands(
        self, obd_module: Any, pids: List[str]
    ) -> Dict[str, Any]:
        commands: Dict[str, Any] = {}
        for pid in pids:
            command = getattr(obd_module.commands, pid, None)
            if command is None:
                logger.warning("PID desconocido para python-obd: %s", pid)
                continue
            commands[pid] = command
        return commands

    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.is_connected()

    def protocol_name(self) -> Optional[str]:
        return self._protocol_name

    def ecu_address(self) -> Optional[str]:
        return self._ecu_address

    def query(self, pid_name: str) -> Optional[Any]:
        reading = self.query_pid(pid_name)
        return reading.value

    def query_pid(self, pid_name: str) -> PIDReading:
        descriptor = get_pid_descriptor(pid_name)
        command = self._commands.get(pid_name)
        if command is None:
            logger.warning("PID no resuelto en python-obd: %s", pid_name)
            return _error_reading(pid_name, descriptor, "UNSUPPORTED")

        try:
            response = self._connection.query(command)
        except Exception:
            logger.exception("Error de comunicación leyendo PID %s", pid_name)
            return _error_reading(
                pid_name, descriptor, "COMMUNICATION_ERROR", ecu=self._ecu_address
            )

        raw = self._raw_from_response(response)

        if response.is_null():
            return _error_reading(
                pid_name,
                descriptor,
                "UNAVAILABLE",
                raw_value=raw,
                ecu=self._ecu_address,
            )

        value = _extract_scalar(response.value)
        ecu = self._extract_ecu(response)
        status = "ZERO" if value == 0 else "VALID"
        unit = descriptor.unit if descriptor else _unit_from_response(response)

        return PIDReading(
            pid=pid_name,
            value=value,
            unit=unit,
            status=status,
            raw_value=raw,
            ecu=ecu,
        )

    def _raw_from_response(self, response: Any) -> Optional[str]:
        if not getattr(response, "messages", None):
            return None
        parts = []
        for msg in response.messages:
            raw = getattr(msg, "raw", None)
            if callable(raw):
                raw = raw()
            if raw:
                parts.append(str(raw))
        return " | ".join(parts) if parts else None

    def _extract_ecu(self, response: Any) -> Optional[str]:
        import obd

        ecu: Optional[str] = None
        if response.messages:
            msg = response.messages[0]
            tx_id = getattr(msg, "tx_id", None)
            if tx_id is not None:
                ecu = f"0x{int(tx_id):03X}"
            else:
                ecu_flag = getattr(msg, "ecu", None)
                if ecu_flag is not None:
                    ecu = _ecu_flag_to_name(ecu_flag, obd)
        if self._ecu_address is None and ecu:
            self._ecu_address = ecu
        return ecu or self._ecu_address

    def get_dtcs(self) -> List[Tuple[str, Optional[str]]]:
        import obd

        if self._connection is None:
            return []
        try:
            response = self._connection.query(obd.commands.GET_DTC)
            if response.is_null():
                return []
            return response.value
        except Exception:
            logger.exception("Error leyendo códigos DTC")
            return []

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {
            "connected": self.is_connected(),
            "port": self._port,
            "protocol": self._protocol_name,
            "protocol_id": self._protocol_id,
            "ecu": self._ecu_address,
            "pids": list(self._commands.keys()),
        }
        try:
            status["obd_status"] = str(self._connection.status())
        except Exception:
            status["obd_status"] = "unknown"
        return status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _error_reading(
    pid: str,
    descriptor: Optional[Any],
    status: str,
    raw_value: Optional[str] = None,
    ecu: Optional[str] = None,
) -> PIDReading:
    return PIDReading(
        pid=pid,
        value=None,
        unit=descriptor.unit if descriptor else None,
        status=status,
        raw_value=raw_value,
        ecu=ecu,
    )


def _extract_scalar(value: Any) -> Optional[float]:
    if value is None:
        return None
    if hasattr(value, "magnitude"):
        magnitude = value.magnitude
        try:
            return float(magnitude)
        except (TypeError, ValueError):
            return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _unit_from_response(response: Any) -> Optional[str]:
    unit = getattr(response, "unit", None)
    return str(unit) if unit is not None else None


def _ecu_flag_to_name(flag: int, obd_module: Any) -> str:
    try:
        ecu = obd_module.protocols.ECU
        if flag == ecu.ENGINE:
            return "ENGINE"
        if flag == ecu.TRANSMISSION:
            return "TRANSMISSION"
        if flag == ecu.ALL:
            return "ALL"
        if flag == ecu.ALL_KNOWN:
            return "ALL_KNOWN"
        if flag == ecu.UNKNOWN:
            return "UNKNOWN"
    except Exception:
        pass
    return f"ECU_FLAG_{flag}"


def _generate_mock_reading(pid_name: str) -> Tuple[str, Optional[float]]:
    raw = f"MOCK:{pid_name}"
    pid_name = pid_name.upper()
    if pid_name == "RPM":
        return raw, float(random.choice([0] * 1 + list(range(700, 3000))))
    if pid_name == "SPEED":
        return raw, float(random.randint(0, 120))
    if pid_name == "COOLANT_TEMP":
        return raw, float(random.randint(70, 100))
    if pid_name == "ENGINE_LOAD":
        return raw, round(random.uniform(0.0, 80.0), 1)
    if pid_name == "THROTTLE_POS":
        return raw, round(random.uniform(0.0, 60.0), 1)
    if pid_name == "INTAKE_TEMP":
        return raw, float(random.randint(15, 45))
    if pid_name == "FUEL_LEVEL":
        return raw, round(random.uniform(20.0, 90.0), 1)
    if pid_name == "MAF":
        return raw, round(random.uniform(5.0, 60.0), 2)
    if pid_name == "INTAKE_PRESSURE":
        return raw, float(random.randint(30, 110))
    if pid_name in ("SHORT_FUEL_TRIM_1", "LONG_FUEL_TRIM_1", "EGR_ERROR"):
        return raw, round(random.uniform(-10.0, 10.0), 2)
    if pid_name == "FUEL_PRESSURE":
        return raw, float(random.randint(200, 400))
    if pid_name == "CONTROL_MODULE_VOLTAGE":
        return raw, round(random.uniform(12.0, 14.8), 2)
    if pid_name == "TIMING_ADVANCE":
        return raw, round(random.uniform(-10.0, 40.0), 1)
    if pid_name == "RUN_TIME":
        return raw, float(random.randint(0, 3600))
    if pid_name in ("O2_B1S1", "O2_B1S2"):
        return raw, round(random.uniform(0.0, 1.0), 3)
    return raw, float(random.randint(0, 255))


# ---------------------------------------------------------------------------
# Factoría
# ---------------------------------------------------------------------------


def create_obd_connection(
    port: str = "",
    pids: Optional[List[str]] = None,
    mock: bool = False,
    protocol: Optional[str] = None,
    timeout: float = 30,
    fast: bool = False,
    **kwargs: Any,
) -> OBDConnection:
    """Crea la conexión adecuada según la configuración."""
    if mock or not _is_obd_available():
        if mock:
            logger.info("Usando conexión OBD-II simulada (mock).")
        else:
            logger.warning(
                "Librería python-obd no disponible; activando modo mock."
            )
        return MockOBDConnection(pids)

    return BluetoothOBDConnection(
        port or "/dev/rfcomm0",
        pids,
        protocol=protocol,
        timeout=timeout,
        fast=fast,
        **kwargs,
    )


# Alias para compatibilidad con código existente que importe ``create_connection``.
create_connection = create_obd_connection
