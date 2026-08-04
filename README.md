# Jarvis On Road

## Objetivo del proyecto

Jarvis On Road es un asistente modular pensado para ejecutarse en una
Raspberry Pi. Este repositorio se desarrolla desde Windows utilizando
Docker, Git y Windsurf, siguiendo un enfoque incremental: primero se
construye la arquitectura base del proyecto y, en fases posteriores, se
irán añadiendo las funcionalidades (IA, voz, hardware, etc.).

Esta primera fase contiene únicamente la estructura inicial del proyecto,
sin lógica de negocio.

## Tecnologías utilizadas

- Python 3.12
- Docker / Docker Compose
- Git

## Cómo ejecutar el proyecto con Docker

```bash
docker compose up --build
```

## Cómo ejecutar el proyecto localmente

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/main.py
```

## Estructura del proyecto

```text
jarvis-on-road/
│
├── src/
│   ├── main.py
│   └── __init__.py
│
├── config/
├── tests/
├── scripts/
├── docs/
│
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
└── LICENSE
```

- **src/**: código fuente de la aplicación. Contiene el punto de entrada `main.py`.
- **config/**: reservado para archivos de configuración futuros.
- **tests/**: reservado para pruebas automatizadas.
- **scripts/**: reservado para scripts auxiliares (despliegue, utilidades, etc.).
- **docs/**: reservado para documentación adicional del proyecto.
