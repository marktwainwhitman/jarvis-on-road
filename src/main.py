"""Punto de entrada principal de Jarvis On Road."""

import socket

__version__ = "0.1.1"


def main() -> None:
    """Inicia la aplicación Jarvis On Road."""
    print("Jarvis On Road iniciando...")
    print(f"Versión {__version__}")
    print(f"Ejecutando en: {socket.gethostname()}")
    print("Sistema listo.")


if __name__ == "__main__":
    main()
