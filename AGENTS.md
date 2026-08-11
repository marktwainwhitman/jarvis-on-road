# Notas para agentes — Jarvis On Road

## Comandos útiles

- Ejecutar tests: `python -m pytest -v`
- Ejecutar localmente en modo mock: `python src/main.py` (por defecto `OBD_MOCK=true`)
- Ejecutar con Docker: `docker compose up --build`

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
