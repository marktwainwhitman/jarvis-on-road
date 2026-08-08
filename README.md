# Jarvis On Road

## Objetivo del proyecto

Jarvis On Road es un asistente modular pensado para ejecutarse en una
Raspberry Pi. Este repositorio se desarrolla desde Windows utilizando
Docker, Git y Windsurf, siguiendo un enfoque incremental: primero se
construye la arquitectura base del proyecto y, en fases posteriores, se
irán añadiendo las funcionalidades (IA, voz, hardware, etc.).

## Fase 1: lectura OBD-II y visualización web

En esta fase el sistema:

1. Se conecta (real o simulado) al puerto OBD-II del coche vía Bluetooth.
2. Lee periódicamente un conjunto básico de PIDs.
3. Evalúa los valores frente a umbrales recomendados y genera alertas.
4. Lee códigos de avería (DTC) del coche y los muestra en la web.
5. Controla luces LED BLE del coche (ELK-BLEDOM / Zengge).
6. Expone los datos a través de una API REST y una página web.
7. Envía los datos y alertas en tiempo real mediante WebSocket.

La página web se puede abrir desde cualquier navegador, incluido el de un
teléfono móvil, sin necesidad de instalar una app nativa. Cuando un valor
sobrepasa un umbral la tarjeta cambia de color, aparece un mensaje de
aviso y, en caso crítico, el móvil vibra.

## Tecnologías utilizadas

- Python 3.12
- Docker / Docker Compose
- Git
- [python-obd](https://python-obd.readthedocs.io/) para comunicación OBD-II
- [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn para el servidor web
- [Bleak](https://bleak.readthedocs.io/) para controlar LEDs por BLE

## Cómo ejecutar el proyecto con Docker

```bash
docker compose up --build
```

La aplicación estará disponible en `http://localhost:8000`.

## Cómo ejecutar el proyecto localmente

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/main.py
```

Abre en el navegador:

```
http://localhost:8000
```

## Configuración mediante variables de entorno

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `OBD_PORT` | Puerto serie del adaptador Bluetooth (p. ej. `COM3` o `/dev/rfcomm0`) | `""` |
| `OBD_MOCK` | `true` para usar datos simulados; `false` para conexión real | `true` |
| `OBD_READ_INTERVAL` | Segundos entre lecturas de PIDs | `1.0` |
| `OBD_DTC_INTERVAL` | Segundos entre lecturas de códigos de avería | `30.0` |
| `OBD_RECONNECT_INTERVAL` | Segundos base entre reintentos de conexión si el adaptador OBD-II no responde o se desconecta | `10.0` |
| `OBD_MAX_RECONNECT_INTERVAL` | Máximo tiempo entre reintentos de conexión OBD (backoff exponencial) | `300.0` |
| `OBD_PIDS` | Lista de PIDs separados por comas | `RPM,SPEED,COOLANT_TEMP,ENGINE_LOAD,THROTTLE_POS,INTAKE_TEMP` |
| `JARVIS_HOST` | Dirección en la que escucha el servidor | `0.0.0.0` |
| `JARVIS_PORT` | Puerto del servidor web | `8000` |
| `JARVIS_LOG_LEVEL` | Nivel de log (`debug`, `info`, `warning`, `error`) | `info` |
| `OBD_ALERT_<PID>_MAX` | Valor máximo recomendado para un PID (p. ej. `OBD_ALERT_RPM_MAX=6000`) | ver `src/obd2/alerts.py` |
| `OBD_ALERT_<PID>_WARN` | Margen sobre el máximo antes de advertencia (p. ej. `OBD_ALERT_RPM_WARN=500`) | ver `src/obd2/alerts.py` |
| `OBD_ALERT_<PID>_CRIT` | Margen sobre el máximo antes de crítico (p. ej. `OBD_ALERT_RPM_CRIT=1000`) | ver `src/obd2/alerts.py` |
| `LED_ENABLED` | `true` para activar el control de luces LED BLE | `false` |
| `LED_MAC` | Dirección MAC de las luces LED ELK-BLEDOM | `""` |
| `LED_BLE_TIMEOUT` | Segundos de timeout para operaciones BLE (conexión/escritura) | `15.0` |

## Endpoints y recursos

- `/` – redirige al panel web.
- `/static/index.html` – panel web para móvil/escritorio.
- `/api/health` – estado básico del sistema.
- `/api/obd/data` – última lectura de PIDs + alertas en JSON.
- `/api/obd/status` – estado de la conexión OBD-II.
- `/api/obd/alerts` – alertas calculadas a partir de la última lectura.
- `/api/obd/recommendations` – valores recomendados por PID.
- `/api/obd/dtcs` – códigos de avería (DTC) leídos del vehículo.
- `/api/leds/status` – estado de las luces LED.
- `/api/leds/on` – encender LEDs.
- `/api/leds/off` – apagar LEDs.
- `/api/leds/color` – cambiar color RGB (`{ "r": 255, "g": 0, "b": 0 }`).
- `/api/leds/brightness` – cambiar brillo (`{ "brightness": 50 }`).
- `/ws` – WebSocket con datos, alertas y DTCs en tiempo real.

## Umbrales por defecto (Kia Ceed 2025 gasolina 1.0 T-GDI)

Los rangos recomendados están orientados a un **Kia Ceed 2025 gasolina
1.0 T-GDI** (3 cilindros turbo, ~120 CV) y definidos en `src/obd2/alerts.py`.

| PID | Mínimo | Máximo recomendado | Advertencia | Crítico |
|---|---|---|---|---|
| `RPM` | 800 rpm | 5000 rpm | > 5500 | > 6000 |
| `SPEED` | 0 km/h | 120 km/h | > 130 | > 150 |
| `COOLANT_TEMP` | 80 °C | 105 °C | > 110 | > 118 |
| `ENGINE_LOAD` | 0 % | 85 % | > 90 | > 95 |
| `INTAKE_TEMP` | 10 °C | 60 °C | > 70 | > 85 |
| `THROTTLE_POS` | 0 % | 100 % | — | — |

Puedes ajustar cualquier PID por variables de entorno sin tocar código, por
ejemplo:

```bash
OBD_ALERT_RPM_MAX=5000
OBD_ALERT_RPM_WARN=500
OBD_ALERT_RPM_CRIT=1000
```

Si más adelante cambias de coche, lo ideal será mover estos umbrales a un
archivo `config/thresholds.json` o añadir perfiles por modelo.

## Uso real con adaptador Bluetooth OBD-II

1. Empareja el adaptador (normalmente un ELM327) con la Raspberry Pi.
2. Crea el puerto serie vía Bluetooth, por ejemplo `/dev/rfcomm0`:
   ```bash
   sudo rfcomm bind 0 XX:XX:XX:XX:XX:XX 1
   ```
3. En `docker-compose.yml` descomenta/configura `OBD_MOCK=false` y
   `OBD_PORT=/dev/rfcomm0`.
4. Arranca con:
   ```bash
   docker compose up --build -d
   ```

## Instalación en Raspberry Pi

### 1. Preparar el sistema

Copia el repositorio en la Raspberry Pi y ejecuta el script de preparación:

```bash
cd jarvis-on-road
sudo bash scripts/setup_pi.sh
```

Esto instala Docker, Docker Compose y activa Bluetooth. Después, **reinicia** la
Raspberry Pi.

### 2. Configurar la Raspberry como punto de acceso WiFi

Para que el móvil se conecte directamente al coche sin depender de una red
externa, ejecuta:

```bash
sudo bash scripts/setup_wifi_ap.sh
```

Por defecto crea la red:

- **SSID:** `JarvisOnRoad`
- **Contraseña:** `Jarvis1234`
- **IP de la Raspberry:** `192.168.4.1`

Puedes cambiarlos con variables de entorno antes de ejecutar el script:

```bash
export JARVIS_AP_SSID=MiCocheAP
export JARVIS_AP_PASSWORD=ClaveSegura123
export JARVIS_AP_IP=10.0.0.1/24
sudo bash scripts/setup_wifi_ap.sh
```

Con esta configuración, el móvil se conecta al WiFi de la Raspberry y abre:

```
http://192.168.4.1:8000
```

La Raspberry no necesita internet para que Jarvis funcione, aunque el móvil
puede seguir usando sus datos móviles si los necesita.

### 3. Emparejar el adaptador OBD-II Bluetooth

1. Enciende el coche y conecta el adaptador ELM327 al puerto OBD-II.
2. Empareja la Raspberry con el adaptador:
   ```bash
   bluetoothctl scan on
   bluetoothctl pair XX:XX:XX:XX:XX:XX
   bluetoothctl trust XX:XX:XX:XX:XX:XX
   ```
3. Crea el puerto serie:
   ```bash
   sudo rfcomm bind 0 XX:XX:XX:XX:XX:XX 1
   ```

### 4. Arrancar Jarvis On Road

Para un arranque manual con el adaptador OBD-II real, primero vincula el
puerto serie Bluetooth y luego levanta el contenedor:

```bash
cd jarvis-on-road
cp .env.example .env
# edita .env con la MAC de tu adaptador OBD-II (OBD_BT_MAC)
sudo bash scripts/obd_rfcomm_bind.sh
OBD_MOCK=false OBD_PORT=/dev/rfcomm0 docker compose up --build -d
```

Con `-d` el contenedor corre en segundo plano. Para ver los logs:

```bash
docker compose logs -f
```

### 5. Arranque automático al encender la Raspberry Pi

El `docker-compose.yml` incluye `restart: unless-stopped`, así que una vez
que el contenedor se ha creado con `docker compose up -d`, Docker lo volverá
a arrancar automáticamente cada vez que la Raspberry Pi se encienda (siempre
que no lo hayas parado tú manualmente con `docker compose stop`).

Solo tienes que asegurarte de que el propio servicio de Docker arranca con el
sistema (esto ya lo hace `scripts/setup_pi.sh`, o puedes activarlo a mano):

```bash
sudo systemctl enable docker
```

Con esto, tras cualquier reinicio o corte de corriente, Jarvis On Road estará
disponible sin tener que ejecutar nada manualmente.

### Notas sobre Bluetooth en Docker

- El acceso a los LEDs BLE se hace a través de BlueZ via D-Bus, por eso se
  monta `/var/run/dbus` y se usa `network_mode: host`.
- El acceso al adaptador OBD-II serie se realiza a través del nodo
  `/dev/rfcomm0`, que debe existir en el host. El script
  `scripts/obd_rfcomm_bind.sh` lo crea; si vas a usar el arranque automático,
  el servicio `jarvis.service` lo ejecuta antes de levantar el contenedor.
  Si `/dev/rfcomm0` no existe, la app seguira funcionando (web y LEDs), pero
  el lector OBD reintentara la conexion periodicamente.
- `privileged: true` es la opción más permisiva; si prefieres reducir
  privilegios, puedes probar a quitarlo y usar `cap_add: [NET_ADMIN]` más
  los `devices` necesarios, pero esto requiere ajustes según tu hardware.

## Luces LED BLE (ELK-BLEDOM / Zengge)

El panel web incluye un control para luces LED del coche que usen el protocolo
ELK-BLEDOM (apps tipo *duoCo Strip*, *Lotus Lantern*, *Happy Lighting*),
con UUIDs:

- **Service UUID:** `0000fff0-0000-1000-8000-00805f9b34fb`
- **Write UUID:** `0000fff3-0000-1000-8000-00805f9b34fb`

### Configuración

Edita `docker-compose.yml` y descomenta/configura:

```yaml
environment:
  - LED_ENABLED=true
  - LED_MAC=BE:FF:F0:01:04:A8  # dirección MAC de tus LEDs
```

O arranca el contenedor con las variables:

```bash
LED_ENABLED=true LED_MAC=BE:FF:F0:01:04:A8 docker compose up --build -d
```

**Importante sobre Docker/Bluetooth:** en Linux, `bleak` habla con el
adaptador Bluetooth a través de BlueZ vía D-Bus, no accediendo directamente a
nodos de dispositivo. Para que los LEDs funcionen dentro del contenedor en la
Raspberry Pi necesitas descomentar en `docker-compose.yml`:

```yaml
network_mode: host
volumes:
  - /var/run/dbus:/var/run/dbus
```

(el montaje de `/dev/rfcomm0` solo es necesario para el adaptador OBD-II por
puerto serie, no para los LEDs BLE).

### Funciones disponibles

- Encender/apagar desde el panel web.
- Selector de color RGB.
- Regulación de brillo (0-100 %).

### Cómo encontrar la MAC de las luces

Desde la Raspberry Pi:

```bash
bluetoothctl scan on
```

Busca un dispositivo llamado `ELK-BLEDOM` o similar y anota su dirección MAC.

## Estructura del proyecto

```text
jarvis-on-road/
|
├── src/
│   ├── main.py              # punto de entrada
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py      # configuración centralizada
│   ├── leds/
│   │   ├── __init__.py
│   │   └── controller.py    # controlador BLE ELK-BLEDOM
│   ├── obd2/
│   │   ├── __init__.py
│   │   ├── alerts.py        # umbrales y evaluación de alertas
│   │   ├── connector.py     # conexión real + mock
│   │   └── reader.py        # lector periódico de PIDs
│   └── web/
│       ├── __init__.py
│       ├── server.py          # FastAPI + WebSocket
│       └── static/
│           └── index.html     # panel web
│
├── config/
├── tests/
├── scripts/
│   ├── setup_pi.sh          # instala Docker y activa Bluetooth
│   └── setup_wifi_ap.sh     # configura la Raspberry como AP WiFi
├── docs/
│
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
└── LICENSE
```

- **src/**: código fuente de la aplicación.
- **src/leds/**: controlador de luces LED BLE.
- **src/obd2/**: comunicación con el adaptador OBD-II y alertas.
- **src/web/**: servidor y panel de visualización.
- **config/**: reservado para archivos de configuración futuros.
- **tests/**: reservado para pruebas automatizadas.
- **scripts/**: scripts auxiliares (despliegue, utilidades, etc.).
- **docs/**: reservado para documentación adicional del proyecto.
