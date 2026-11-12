# DashNode Backend API

> **Arquetipo Backend DAS — Arquitectura Hexagonal y Trunk-Based Development**

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Framework](https://img.shields.io/badge/framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![ORM](https://img.shields.io/badge/ORM-SQLAlchemy%202.0-red.svg)](https://www.sqlalchemy.org/)
[![Architecture](https://img.shields.io/badge/architecture-Hexagonal%20%2F%20Ports%20%26%20Adapters-orange.svg)](#arquitectura-del-sistema)
[![Git Strategy](https://img.shields.io/badge/git%20strategy-Trunk--Based%20Development-success.svg)](docs/TRUNK_BASED_DEVELOPMENT.md)

- [Guía de despliegue (Render + Supabase)](./docs/deployment-guide.md)

---

## Arquitectura del Sistema

El backend de DashNode está construido bajo los principios de **Arquitectura Hexagonal (Ports & Adapters)** y **Clean Architecture**, estructurado como un **Monolito Modular** desacoplado:

```
app/
├── modules/
│   ├── auth/            # Módulo de Autenticación y Cuentas de Usuario
│   ├── projects/        # Módulo de Gestión de Proyectos y Miembros
│   ├── tasks/           # Módulo de Tareas y Máquina de Estados (Draft -> Active -> ...)
│   └── notifications/   # Módulo de Notificaciones In-App
│       ├── domain/          # Entidades puras y Puertos (Protocols/Interfaces)
│       ├── application/     # Casos de Uso, DTOs y Orquestación de Negocio
│       ├── infrastructure/  # Modelos SQLAlchemy, Repositorios (Adaptadores)
│       └── api/             # Routers FastAPI, Endpoints REST y Schemas HTTP
├── shared/
│   ├── domain/              # Clases base, Value Objects e Interfaces comunes
│   ├── application/         # Contratos compartidos (Clock, IdGenerator, CurrentUser)
│   └── infrastructure/      # SQLAlchemy Engine, Base declarativa, Argon2, UUID, Clock
└── orchestration/           # Inyección de Dependencias modular y Middleware de Seguridad
```

### Reglas de Arquitectura Forzadas (Import Linter)
1. **BR-1 (API Purity)**: Los Routers de la API nunca importan directamente modelos ORM o la base de datos; interactúan exclusivamente mediante Casos de Uso y DTOs.
2. **BR-2 (Domain Purity)**: Las capas de Dominio son 100% puras (sin dependencias de FastAPI, SQLAlchemy o librerías de infraestructura).
3. **BR-4 (Module Isolation)**: Aislamiento estricto entre módulos. No existen imports cruzados entre módulos de infraestructura.

---

## Estrategia Git Trunk (Trunk-Based Development)

Este proyecto adopta **Trunk-Based Development (TBD)** como modelo oficial de versionamiento e integración continua:

- **`main` es el Trunk**: Debe estar permanentemente en estado **verde** (desplegable en producción en cualquier instante).
- **Ramas de corta duración (*Short-lived branches*)**: Ramas tipo `feat/nombre` o `fix/nombre` con vida menor a 24-48 horas.
- **Integración continua diaria**: Integración de código al menos una vez al día con PRs pequeños (< 300 líneas).
- **Quality Gates obligatorias**: Todos los commits y PRs deben superar el 100% de los controles automáticos de calidad en GitHub Actions (`trunk-ci.yml`).

 **Consulta la guía completa de contribución y flujo de trabajo:** [Guía Trunk-Based Development](docs/TRUNK_BASED_DEVELOPMENT.md).

---

## Quality Gates Locales y en CI

El proyecto mantiene una política estricta de **cero advertencias y cero errores**:

| Control | Herramienta | Comando |
|---|---|---|
| **Linter** | Ruff | `python -m ruff check .` |
| **Formateador** | Ruff Format | `python -m ruff format --check .` |
| **Tipado Estricto** | Mypy (Strict) | `python -m mypy .` |
| **Contratos de Arquitectura** | Import Linter | `python -m importlinter.cli` |
| **Suite de Pruebas y Cobertura** | Pytest + Coverage | `python -m pytest --cov=app` |
| **Integridad de Migraciones** | Alembic | `python -m alembic upgrade head --sql` |

Para ejecutar todas las validaciones de una sola vez:
```bash
make check
```

### Activación de Git Hooks Locales
Para ejecutar los quality gates automáticamente antes de cada commit:
```bash
# En Windows (PowerShell)
.\scripts\setup-hooks.ps1

# En Linux / macOS / Bash
make hooks-install
```

---

## Puesta en Marcha (Local)

### 1. Requisitos
- Python 3.12+ y Docker (para PostgreSQL local; las pruebas de API usan SQLite en memoria).

### 2. Configuración (secretos nunca en el repositorio)
```bash
python -m venv .venv
.venv\Scripts\activate              # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -e ".[dev]"

python scripts/generate_env.py      # crea .env (ignorado por git) con contraseñas aleatorias
```
`.env.example` documenta cada variable. `.env` nunca se versiona; `scripts/scan_secrets.py` (hook
`pre-commit` y CI) bloquea cualquier secreto o archivo `.env` en un commit.

### 3. Base de datos, migraciones y datos locales
```bash
docker compose up -d db             # PostgreSQL 16 en 127.0.0.1:${POSTGRES_HOST_PORT:-5434}
alembic upgrade head
python -m app.cli.seed              # admin / desarrollador / cuenta desactivada (credenciales en .env)
```

### 4. Servidor de desarrollo
```bash
uvicorn app.main:app --reload
```
- Swagger UI: http://localhost:8000/docs · Liveness: `/health` · Readiness (BD): `/health/ready`
- API de autenticación documentada en [docs/api-auth.md](docs/api-auth.md).

### 5. Todo en contenedores (API + PostgreSQL)
```bash
docker compose up --build -d        # el entrypoint aplica las migraciones al arrancar
docker compose exec api python -m app.cli.seed
```
La red `dashnode-net` permite que el contenedor del frontend alcance la API como `dashnode-api:8000`.

### 6. Pruebas
```bash
pytest                              # unit + application + api (SQLite) + integration (PostgreSQL si TEST_POSTGRES_URL)
make check                          # secretos + ruff + mypy + import-linter + pytest con cobertura >= 80 %
```
Las pruebas de integración crean y eliminan bases temporales en el servidor de `TEST_POSTGRES_URL`.