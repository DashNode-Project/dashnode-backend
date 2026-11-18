# FIX-01 — Registro de intervención (estado parcial)

**Fecha:** 2026-11-17 (actualizado)  
**Rama:** `feature/ep-13-metricas-valoracion-ia`  
**Repositorios:** `dashnode-backend`, `dashnode-frontend`

## Resumen ejecutivo

Intervención orientada a estabilizar persistencia (Supabase primario vía **pooler** + fallback local), corregir métricas de salud, DoR/DoD, KB del sistema y mejoras UX.  
**2026-11-17:** Supabase operativo; migración `025`; seed usuarios + 31 FAQ + proyectos **Helix Health Portal** y **OrbitLogistics TMS** en nube; login manager verificado; push en `feature/ep-13-metricas-valoracion-ia`. Varios ítems UX FIX-01 siguen **pendientes** (§11).

## 1. Problemas identificados y causas raíz

| ID | Problema | Causa raíz | Estado |
|----|----------|------------|--------|
| 2.1 | `ConnectionTimeout` contra PostgreSQL | URL remota inalcanzable / timeout de pool; motor único sin contingencia | **Implementado** (selector primary/fallback) |
| 2.3 | Progreso / issues en resumen incorrectos | Progreso limitado al sprint activo; `open_issues` contaba tareas en corrección | **Implementado** (progreso global; issues = fixes abiertos) |
| 2.9 | Pocas tareas en Mis tareas | Filtro de proyecto derivado solo del subconjunto cargado | **Implementado** (UI: `listProjects` + persistencia) |
| 2.7 | Sin DoR/DoD en HUs | Columnas inexistentes en modelo | **Implementado** (migración + API); **UI pendiente** |
| 2.10 | Asistente sin manual | Sin tabla ni búsqueda persistente | **Parcial** (API + seed script + ramal orquestador) |
| §3 | Datos demo 2 proyectos | No ejecutado en este ciclo | **Pendiente** |

## 2. Correcciones realizadas (evidencia)

- `app/shared/infrastructure/database_provider.py`, `database.py`: elección única de motor; `DATABASE_FALLBACK_URL`, pool/timeouts.
- `app/main.py`: lifespan `initialize_database()`; `/health/ready` expone `database_provider`.
- `project_health_adapter.py`: progreso sobre todo el backlog; issues abiertos vía `fixes`.
- `ProjectHealthDTO` + campos de conteo para frontend.
- `ListMyTasksUseCase`: `epic` y `sprint` en respuesta.
- Migración `025_fix01_dor_dod_kb`: DoR/DoD + `system_knowledge_entries`.
- `system_knowledge_routes.py`, `scripts/seed_system_knowledge_faq.py` (31 FAQ).
- Asistente: búsqueda manual, DoR/DoD en listado de HUs, `list_project_issues` en adapter.

## 3. Frontend (evidencia)

- Resumen sin alta/baja de miembros; teaser de equipo; tarjetas de salud extendidas.
- Equipo: grid/tabla, búsqueda, gestión de miembros, preview.
- Mis tareas: localStorage, vista tabla, proyectos vía API.
- Usuarios: preview seguro.
- Atajos: modal + manual compartido.

## 4. Variables de entorno (sin secretos)

| Variable | Uso |
|----------|-----|
| `DATABASE_URL` | PostgreSQL primario (Supabase recomendado, `sslmode=require`) |
| `DATABASE_FALLBACK_URL` | Contingencia local |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | Timeout de conexión |
| `DATABASE_POOL_*` | Pool SQLAlchemy |
| `API_GEMINI`, `API_TRANSCRIPTION_WHISPER`, `AI_GEMINI_TRANSCRIBE_*`, límites diarios | Ya en `config.py` / `.env.example` (sin cambio de semántica) |

## 5. Pruebas ejecutadas

| Suite | Resultado |
|-------|-----------|
| Backend `pytest tests/unit tests/application` | **345 passed** |
| Backend `ruff check` + `ruff format` | **OK** (tras FIX-01) |
| Frontend `npm run typecheck` | **OK** |
| Frontend `npm run lint` | **OK** |
| Makefile `check` completo backend | **No ejecutado** (cobertura 80 %, mypy, arch, integration) |
| E2E Manager + seed 2 proyectos | **No ejecutado** |

## 6. Migraciones

- `025_fix01_dor_dod_kb` — **creada**; aplicar con `alembic upgrade head` contra el proveedor activo.

## 7. Pendientes / bloqueados

- Dos proyectos demo completos (§3 FIX-01).
- UI Markdown DoR/DoD, dnd-kit entre épicas, guardado manual de tareas, sprints/burndown, vistas tabla en tareas del proyecto, reunión recomendada en asistente.
- Ejecutar seeds: `python scripts/seed_system_knowledge_faq.py`.
- Validación login contra Supabase real en entorno del usuario.
- `make check` integral y documentación SAD/config extendida.

## 8. Trazabilidad requerimiento → estado

| Req | Estado |
|-----|--------|
| 2.1 BD Supabase + fallback | Implementado / validación parcial |
| 2.2 IA transcripción | Sin cambio (híbrido ya existía) |
| 2.3 Resumen | Parcial (API + UI básica) |
| 2.4 Equipo | Implementado (frontend) |
| 2.5 Usuarios preview | Implementado |
| 2.6 Tareas | Pendiente |
| 2.7 HUs DoR/DoD | Backend OK / UI pendiente |
| 2.8 Sprints | Pendiente |
| 2.9 Mis tareas | Implementado (UI + API epic/sprint) |
| 2.10 Asistente + KB | Parcial |
| 2.11 Usabilidad | Parcial (atajos/tooltips) |
| §3 Demo | Pendiente |
| §5 QA completo | Pendiente |