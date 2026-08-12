# Notas para agentes — Jarvis On Road

## Comandos útiles

- Ejecutar tests: `python -m pytest -v`
- Ejecutar localmente en modo mock: `python src/main.py` (por defecto `OBD_MOCK=true`)
- Ejecutar con Docker: `docker compose up --build`
- Descubrir PIDs en modo mock: `python -m src.obd2.discovery --mock`
- Ejecutar collector autónomo en modo mock: `python -m src.obd2.collector --mock --interval 1.0`
- Ejecutar collector autónomo en la Raspberry: `OBD_MOCK=false python -m src.obd2.collector`
- Emparejar vLinker MC+ una sola vez: `./scripts/pair_vlinker.sh`
- Diagnóstico Bluetooth en Raspberry: `sudo ./scripts/diagnose_bluetooth.sh`
- Diagnóstico serie OBD en Raspberry (tras bind): `python3 scripts/diagnose_obd.py`
- Forzar binding manual del vLinker: `sudo ./scripts/obd_rfcomm_bind.sh`
- Instalar servicios systemd autónomos:
  ```bash
  sudo cp scripts/obd_rfcomm_keepalive.service /etc/systemd/system/
  sudo cp scripts/jarvis.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable obd_rfcomm_keepalive.service jarvis.service
  sudo systemctl start obd_rfcomm_keepalive.service jarvis.service
  ```

## Fase actual: OBD-II real a CSV

La arquitectura OBD se mantiene modular:

- `src/obd2/connector.py` define `OBDConnection`/`BluetoothOBDConnection`/`MockOBDConnection`.
- `src/obd2/csv_logger.py` escribe `data/obd/YYYY-MM-DD.csv`.
- `src/obd2/discovery.py` prueba PIDs y muestra estado.
- `src/obd2/collector.py` es el punto de entrada autónomo para la Raspberry.

Restricciones de seguridad: todas las comunicaciones con la ECU son **solo lectura**. No se implementa escritura, borrado de DTC, codificación, calibración ni activación de actuadores.

No continuar con SQLite, FastAPI, WebSocket, PWA ni análisis predictivo hasta que se
valide establemente:

Raspberry Pi Zero 2 W -> Bluetooth -> Vgate vLinker MC+ -> Kia Ceed -> ECM -> CSV.

## Estructura de la PWA

La interfaz es una PWA vanilla (HTML/CSS/JS) servida por FastAPI:

- `src/web/static/index.html` — punto de entrada.
- `src/web/static/manifest.json` — manifest de instalación.
- `src/web/static/sw.js` — Service Worker para caché offline.
- `src/web/static/css/main.css` — estilos.
- `src/web/static/js/*.js` — módulos JavaScript.

Endpoints estáticos clave para la PWA:

- `/manifest.json`
- `/sw.js`
- `/static/index.html`

## Restricciones del frontend

- El frontend no accede al hardware.
- BLE y OBD se controlan exclusivamente desde el backend.
- Las comunicaciones con LEDs y OBD pasan por las APIs REST/WebSocket de FastAPI.
