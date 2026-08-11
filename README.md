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
| `JARVIS_DB_PATH` | Ruta del fichero SQLite con el histórico de datos OBD-II | `data/jarvis.db` |
| `JARVIS_DB_RETENTION_DAYS` | Días que se conservan las lecturas en crudo antes de purgarse (los agregados horarios se conservan siempre) | `30` |
| `LED_AUTO_MODE` | `true` para activar el encendido/apagado automático de LEDs según amanecer/atardecer | `false` |
| `LED_AUTO_LAT` / `LED_AUTO_LON` | Latitud/longitud aproximadas para calcular la salida y puesta de sol (por defecto, zona Huelva-Sevilla-Cádiz) | `37.2` / `-6.4` |
| `LED_AUTO_TZ` | Zona horaria usada para el cálculo de amanecer/atardecer | `Europe/Madrid` |
| `LED_AUTO_CHECK_INTERVAL` | Segundos entre comprobaciones de si toca cambiar de día a noche o viceversa | `60.0` |
| `LED_AUTO_PRE_LIGHT_MINUTES` | Minutos que se anticipa el encendido respecto al atardecer real (el apagado sigue ocurriendo en el amanecer real) | `30.0` |

## Endpoints y recursos

- `/` – redirige al panel web.
- `/static/index.html` – panel web para móvil/escritorio.
- `/manifest.json` – manifest de la PWA.
- `/sw.js` – Service Worker para funcionamiento offline.
- `/static/css/main.css` – estilos de la PWA.
- `/static/js/*.js` – módulos JavaScript de la interfaz.
- `/api/health` – estado básico del sistema.
- `/api/obd/data` – última lectura de PIDs + alertas en JSON.
- `/api/obd/status` – estado de la conexión OBD-II.
- `/api/obd/alerts` – alertas calculadas a partir de la última lectura.
- `/api/obd/recommendations` – valores recomendados por PID.
- `/api/obd/dtcs` – códigos de avería (DTC) leídos del vehículo.
- `/api/obd/history?pid=RPM&hours=1` – lecturas en crudo de un PID en las últimas N horas.
- `/api/obd/stats?pid=RPM&days=7` – estadísticas horarias (mín/máx/media) de un PID en los últimos N días.
- `/api/obd/events?days=7&type=alert|dtc` – historial de eventos (alertas activadas/desactivadas, DTCs nuevos).
- `/api/leds/status` – estado de las luces LED.
- `/api/leds/on` – encender LEDs.
- `/api/leds/off` – apagar LEDs.
- `/api/leds/color` – cambiar color RGB (`{ "r": 255, "g": 0, "b": 0 }`).
- `/api/leds/brightness` – cambiar brillo (`{ "brightness": 50 }`).
- `/api/leds/auto` – activar/desactivar el modo automático día/noche (`{ "enabled": true }`).
- `/ws` – WebSocket con datos, alertas y DTCs en tiempo real.

## PWA (Progressive Web App)

La interfaz está construida como PWA y se sirve desde el propio backend:

- `/manifest.json` – configuración de instalación.
- `/sw.js` – Service Worker que cachea los recursos estáticos para funcionar offline.
- `/static/index.html` – interfaz modular en HTML/CSS/JavaScript vanilla.

Para instalar la app en Android:

1. Conecta el móvil al Wi-Fi `JarvisOnRoad` de la Raspberry.
2. Abre `http://192.168.4.1:8000` en Chrome/Edge/Samsung Internet.
3. Toca "Instalar" cuando aparezca el banner o usa el botón "Instalar" de la barra inferior.

Una vez instalada, la app funciona en modo standalone sin necesidad de Internet.
La interfaz se mantiene disponible offline gracias al caché del Service Worker.
Las lecturas en vivo de OBD-II y el control de LEDs requieren estar conectado
a la red de Jarvis.

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

La MAC del adaptador OBD-II Bluetooth de este coche (`04:25:E8:5B:01:EB`) ya
está configurada por defecto en `docker-compose.yml` y en
`scripts/obd_rfcomm_bind.sh`, así que **no hace falta tocar nada**: basta con
emparejar el adaptador una vez (paso 3 de la instalación) y hacer
`git pull` + `docker compose up -d --build` para que todo funcione. Solo
necesitas crear un `.env` (a partir de `.env.example`) si algún día cambias
de adaptador OBD-II o de coche.

1. Empareja el adaptador (normalmente un ELM327) con la Raspberry Pi (ver
   sección "Emparejar el adaptador OBD-II Bluetooth" más abajo).
2. Arranca con:
   ```bash
   docker compose up --build -d
   ```

El binding a `/dev/rfcomm0` lo hace automáticamente
`scripts/obd_rfcomm_bind.sh` (a mano o vía `jarvis.service` en el arranque
automático) usando esa MAC por defecto.

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

La MAC de este adaptador (`04:25:E8:5B:01:EB`) ya está puesta por defecto en
el proyecto; solo falta emparejarlo una vez con la Raspberry (el pairing es
un estado del sistema Bluetooth, no algo que viaje con el repo):

1. Enciende el coche y conecta el adaptador ELM327 al puerto OBD-II.
2. Empareja la Raspberry con el adaptador:
   ```bash
   bluetoothctl scan on
   bluetoothctl pair 04:25:E8:5B:01:EB
   bluetoothctl trust 04:25:E8:5B:01:EB
   ```

No hace falta ejecutar `rfcomm bind` a mano: lo hace
`scripts/obd_rfcomm_bind.sh` automáticamente (ver siguiente paso).

### 4. Arrancar Jarvis On Road

Con el adaptador ya emparejado, un arranque manual es tan sencillo como:

```bash
cd jarvis-on-road
sudo bash scripts/obd_rfcomm_bind.sh
docker compose up --build -d
```

No es necesario crear un `.env`: `OBD_MOCK=false`, `OBD_PORT=/dev/rfcomm0` y
la MAC del adaptador ya están fijados en `docker-compose.yml` y en el propio
script de binding.

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
- El contenedor corre como `root` (no como usuario no-root) porque
  `docker-compose.yml` monta el repo del host como bind mount (`.:/app`):
  con un usuario no-root, `data/jarvis.db` fallaría con
  `sqlite3.OperationalError: unable to open database file` salvo que su
  UID/GID coincidieran exactamente con los del usuario propietario de la
  carpeta en el host. Dado que ya se usa `privileged: true`, ejecutar como
  root no añade una superficie de riesgo significativa adicional en este
  despliegue de un solo dispositivo personal.

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
- **Modo automático día/noche**: enciende los LEDs al anochecer y los apaga
  al amanecer, calculando la salida y puesta de sol para una ubicación
  aproximada (no requiere sensor de luz ni GPS: el OBD-II del coche no
  expone esa información). Se activa con `LED_AUTO_MODE=true` o desde el
  interruptor "Automático" en la pestaña de LEDs de la PWA. Por defecto la
  ubicación está fijada a la zona Huelva-Sevilla-Cádiz (`LED_AUTO_LAT`/
  `LED_AUTO_LON`, con un margen de error aceptable de ~30 min); si usas el
  coche habitualmente en otra zona, ajusta esas variables. El encendido se
  anticipa `LED_AUTO_PRE_LIGHT_MINUTES` (30 min por defecto) respecto al
  atardecer real, para que las luces ya estén encendidas cuando empieza a
  oscurecer en vez de esperar a la puesta de sol exacta; el apagado sigue
  ocurriendo en el amanecer real. El modo manual (botones on/off) sigue
  funcionando en cualquier momento; al reactivar el modo automático, este
  vuelve a sincronizar el estado de los LEDs con el sol en la siguiente
  comprobación (`LED_AUTO_CHECK_INTERVAL`, 60 s por defecto).

### Cómo encontrar la MAC de las luces

Desde la Raspberry Pi:

```bash
bluetoothctl scan on
```

Busca un dispositivo llamado `ELK-BLEDOM` o similar y anota su dirección MAC.

## Histórico de datos OBD-II (SQLite)

Además de la última lectura en vivo, Jarvis On Road guarda un histórico en
una base de datos SQLite (`src/storage/`), pensado para funcionar bien en la
tarjeta SD de la Raspberry Pi:

- **Lecturas en crudo** (`readings`, un valor por PID y ciclo de lectura):
  se conservan solo `JARVIS_DB_RETENTION_DAYS` días (30 por defecto). Con la
  configuración por defecto (6 PIDs, 1 lectura/segundo) esto son varios GB al
  mes, así que no conviene guardarlas para siempre.
- **Estadísticas horarias** (`hourly_stats`: mín/máx/media por PID y hora):
  se agregan automáticamente cada hora a partir de las lecturas en crudo y
  **se conservan indefinidamente** (ocupan muy poco espacio: unas decenas de
  miles de filas al año). Son la fuente pensada para tendencias a medio/largo
  plazo y análisis preventivo.
- **Eventos** (`events`): solo se registra cuando una alerta empieza/termina
  o aparece un código DTC nuevo, para no duplicar una fila por cada ciclo de
  lectura mientras la alerta esté activa.

Las escrituras se bufferizan en memoria y se vuelcan a SQLite en lotes desde
un hilo de fondo (por defecto cada 5s), para no bloquear el hilo lector de
OBD-II con I/O de disco y reducir el desgaste de escritura de la SD.

La base de datos vive en `data/jarvis.db` (configurable con `JARVIS_DB_PATH`)
y no se versiona en git; en Docker persiste gracias al bind mount `.:/app`
del `docker-compose.yml`.

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
│   │   ├── controller.py    # controlador BLE ELK-BLEDOM
│   │   └── scheduler.py     # automatización día/noche (amanecer/atardecer)
│   ├── obd2/
│   │   ├── __init__.py
│   │   ├── alerts.py        # umbrales y evaluación de alertas
│   │   ├── connector.py     # conexión real + mock
│   │   └── reader.py        # lector periódico de PIDs
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py      # conexión y esquema SQLite
│   │   └── history.py       # buffer, rollup horario, purga y consultas
│   └── web/
│       ├── __init__.py
│       ├── server.py          # FastAPI + WebSocket
│       └── static/
│           └── index.html     # panel web
│
├── config/
├── data/                    # base de datos SQLite (no versionada)
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
