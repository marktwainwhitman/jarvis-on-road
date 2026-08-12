#!/usr/bin/env python3
"""Diagnóstico de comunicación OBD-II a bajo nivel por /dev/rfcomm0.

Requiere que el vLinker ya esté vinculado (por ejemplo mediante
scripts/obd_rfcomm_bind.sh). Envía comandos AT y un PID de prueba para
verificar que la línea serie funciona antes de arrancar python-obd.

Uso en Raspberry Pi:
    python3 scripts/diagnose_obd.py
"""

import argparse
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.config import SETTINGS


def diagnose(port: str, baudrate: int = 38400, timeout: float = 5.0) -> int:
    try:
        import serial
    except ImportError:
        print("ERROR: pyserial no está instalado. Ejecuta: pip install pyserial")
        return 1

    print(f"Abriendo {port} (baudrate={baudrate}, timeout={timeout})...")
    try:
        s = serial.Serial(port, baudrate=baudrate, timeout=timeout)
    except Exception as exc:
        print(f"ERROR: no se pudo abrir {port}: {exc}")
        print("Comprueba que scripts/obd_rfcomm_bind.sh ha creado /dev/rfcomm0.")
        return 1

    commands = [
        ("ATZ", 2.0, "Reset del adaptador"),
        ("ATE0", 0.5, "Echo off"),
        ("ATL1", 0.5, "Salto de línea"),
        ("ATS0", 0.5, "Espacios off"),
        ("ATH1", 0.5, "Headers on"),
        ("ATSP6", 0.5, "Forzar protocolo ISO 15765-4 CAN 11-bit 500"),
        ("0100", 2.0, "PID de prueba (PIDs soportados [01-20])"),
        ("010C", 1.0, "PID RPM"),
    ]

    print()
    for cmd, wait, desc in commands:
        print(f">>> {cmd}   # {desc}")
        s.write((cmd + "\r").encode())
        time.sleep(wait)
        raw = s.read(s.in_waiting or 1024)
        text = raw.decode(errors="replace").replace("\r", "\\r").replace("\n", "\\n")
        print(f"<<< {text!r}")
        print()

    s.close()
    print("Diagnóstico finalizado.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico serie OBD-II")
    parser.add_argument("--port", default=SETTINGS.obd_port, help="Puerto serie")
    parser.add_argument("--baudrate", type=int, default=38400, help="Baudrate")
    parser.add_argument("--timeout", type=float, default=5.0, help="Timeout lectura")
    args = parser.parse_args()

    if not args.port:
        args.port = "/dev/rfcomm0"

    return diagnose(args.port, args.baudrate, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
