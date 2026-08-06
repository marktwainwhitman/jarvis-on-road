"""Conectores OBD-II: real (python-obd) y simulado (mock)."""

import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _is_obd_available() -> bool:
    try:
        import obd  # noqa: F401
        return True
    except Exception:
        return False


class OBD2Connection(ABC):
    """Interfaz común para conexiones OBD-II."""

    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @abstractmethod
    def query(self, pid_name: str) -> Optional[Any]:
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


class OBD2MockConnection(OBD2Connection):
    """Conexión simulada que genera valores de ejemplo."""

    def __init__(self, pids: list[str]):
        self._pids = pids
        self._connected = True
        self._start_time = time.time()

    def is_connected(self) -> bool:
        return self._connected

    def query(self, pid_name: str) -> Optional[Any]:
        if not self._connected:
            return None
        return _generate_mock_value(pid_name)

    def close(self) -> None:
        self._connected = False

    def status(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "port": "MOCK",
            "pids": self._pids,
            "elapsed_seconds": round(time.time() - self._start_time, 1),
        }

    def get_dtcs(self) -> List[Tuple[str, Optional[str]]]:
        # En modo simulado devuelve ocasionalmente un DTC de ejemplo para poder
        # probar la visualización de códigos de avería.
        if random.random() < 0.15:
            return [("P0301", "Fallo de encendido cilindro 1 (simulado)")]
        return []


class OBD2RealConnection(OBD2Connection):
    """Conexión real usando la librería python-obd."""

    def __init__(self, port: str, pids: list[str]):
        import obd

        self._port = port
        self._pids = pids
        self._commands = self._resolve_commands(obd, pids)
        logger.info("Conectando a OBD-II en puerto %s...", port)
        self._connection = obd.OBD(port)
        logger.info("Estado de conexión OBD-II: %s", self._connection.status())

    def _resolve_commands(self, obd_module, pids: list[str]) -> Dict[str, Any]:
        commands = {}
        for pid in pids:
            command = getattr(obd_module.commands, pid, None)
            if command is None:
                logger.warning("PID desconocido: %s", pid)
                continue
            commands[pid] = command
        return commands

    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.is_connected()

    def query(self, pid_name: str) -> Optional[Any]:
        command = self._commands.get(pid_name)
        if command is None:
            return None
        response = self._connection.query(command)
        if response.is_null():
            return None
        return response.value

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def get_dtcs(self) -> List[Tuple[str, Optional[str]]]:
        import obd

        if self._connection is None:
            return []
        try:
            response = self._connection.query(obd.commands.GET_DTC)
            if response.is_null():
                return []
            # python-obd devuelve una lista de tuplas (codigo, descripcion).
            return response.value
        except Exception:
            logger.exception("Error leyendo códigos DTC")
            return []

    def status(self) -> Dict[str, Any]:
        return {
            "connected": self.is_connected(),
            "port": self._port,
            "pids": list(self._commands.keys()),
        }


def _generate_mock_value(pid_name: str) -> Any:
    pid_name = pid_name.upper()
    if pid_name == "RPM":
        return random.randint(700, 3000)
    if pid_name == "SPEED":
        return random.randint(0, 120)
    if pid_name == "COOLANT_TEMP":
        return random.randint(70, 100)
    if pid_name == "ENGINE_LOAD":
        return round(random.uniform(10.0, 80.0), 1)
    if pid_name == "THROTTLE_POS":
        return round(random.uniform(0.0, 60.0), 1)
    if pid_name == "INTAKE_TEMP":
        return random.randint(15, 45)
    if pid_name == "FUEL_LEVEL":
        return round(random.uniform(20.0, 90.0), 1)
    return random.randint(0, 255)


def create_connection(port: str, pids: list[str], mock: bool = False) -> OBD2Connection:
    """Factoría que crea la conexión adecuada según la configuración."""
    if mock or not _is_obd_available():
        if mock:
            logger.info("Usando conexión OBD-II simulada (mock).")
        else:
            logger.warning("Librería python-obd no disponible; activando modo mock.")
        return OBD2MockConnection(pids)

    return OBD2RealConnection(port, pids)
