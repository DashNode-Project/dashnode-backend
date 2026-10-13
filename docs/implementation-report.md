# Informe de implementación — Backend EP-01 Autenticación y sesiones

Rama: `feature/ep-01-auth-sessions` (base `develop`, que parte de `main`). Un commit por HU más cimientos, endurecimiento y documentación.

## Resumen por HU

| HU | Estado | Commit (asunto) |
|---|---|---|
| Cimientos | Hecho | `foundation`: config sin secretos, errores, CSRF/cabeceras, migraciones, Docker, CI, hooks |
| HU_DN_01_02 Registro Gerente | Hecho | `feat(HU_DN_01_02)` |
| HU_DN_01_03 Login | Hecho | `feat(HU_DN_01_03)` |
| HU_DN_01_04 Logout | Hecho | `feat(HU_DN_01_04)` |
| HU_DN_01_05 Sesión al recargar | Hecho | `feat(HU_DN_01_05)` |
| HU_DN_01_06–10 Reset, authz, admin | Hecho | `feat(auth): HU_DN_01_06-10 password reset, authz and admin flows` |
| EP-02 HU_DN_01_11–16 Usuarios | Hecho | `feat(HU_DN_01_11)` + docs HU_12–16 en `feature/ep-02-users-roles` |
| HU_DN_01_01 Landing | N/A en backend | Solo frontend |

## Resultados de validación (local, última ejecución)

| Control | Resultado |
|---|---|
| `pytest` (unit, application, api, integration) | 228 pruebas, 0 fallos, 0 omitidas |
| Cobertura (`--cov=app`, umbral 80 %) | 94.89 % |
| `ruff check` / `ruff format --check` (incluye reglas S, DTZ, T20, TID251) | Sin hallazgos |
| `mypy --strict` | Sin errores |
| `import-linter` (BR-1, BR-2, BR-4 transitivo) | Contratos cumplidos |
| `scripts/scan_secrets.py --all` | Sin secretos |
| `pip-audit` | Sin vulnerabilidades conocidas |
| PostgreSQL 16 real (Docker) | Registro concurrente (un solo ganador), logins concurrentes (límite nunca excedido), migraciones 001→002 |
| Contenedor `api` + `db` (docker compose) | Migraciones aplicadas al arrancar; `/health/ready` 200 |

## Capacidades de validación utilizadas

Pruebas unitarias del dominio con **hypothesis** (propiedades de normalización de correo y contraseñas), pruebas de
casos de uso con dobles y reloj controlado, pruebas de API extremo a extremo con SQLite, pruebas de integración con
PostgreSQL real y concurrencia, análisis estático (ruff/mypy/import-linter), auditoría de dependencias, escaneo de
secretos y verificación de que la API no devuelve hashes, tokens ni valores enviados por el usuario.

## Seguridad aplicada

- Contraseñas con Argon2id (sal por hash); verificación con hash ficticio para correos inexistentes (sin diferencia de tiempos útil para enumerar).
- Token de sesión de 256 bits; solo el SHA-256 se almacena. Cookie `HttpOnly` + `SameSite=Lax` (+ `Secure` obligatorio en producción).
- Expiración absoluta de 8 h, revocación en logout, validación por petición en servidor (usuario desactivado = acceso denegado).
- Límite de 5 intentos/15 min por cuenta, atómico bajo concurrencia, sin ampliarse por intentos rechazados.
- Registro público limitado al rol Gerente (el arquetipo permitía elegir cualquier rol: escalada de privilegios cerrada).
- CSRF por lista de orígenes permitidos; cabeceras de seguridad; `Cache-Control: no-store` en `/api/*`.
- Errores sin eco de valores ni trazas; SQL nunca se registra (los parámetros contienen hashes y digests).
- Sin secretos en código ni en el repositorio: `.env` generado localmente (ignorado), `.env.example` solo con marcadores; hook y CI con escaneo de secretos.

## Supuestos y desviaciones

Ver la tabla «Decisiones y supuestos» en `docs/user-stories.md`. Pendiente fuera del alcance: recuperación de contraseña
(las variables `SMTP_*`, `FRONTEND_BASE_URL` y `PASSWORD_RESET_TTL_MINUTES` ya están preparadas en `.env.example`).

## Cómo reproducir

```bash
python scripts/generate_env.py && docker compose up -d db && alembic upgrade head
pytest --cov=app --cov-fail-under=80 && make check
```

## Validación (Integrador) — 2026-10-11

Re-ejecución de gates y E2E con la pila real (API + Postgres + nginx):

| Control | Resultado |
|---|---|
| `pytest --cov=app --cov-fail-under=80` | 218 passed, 94.77 % |
| ruff / mypy --strict / import-linter / scan_secrets | Verde |
| `node scripts/e2e-stack.mjs` (desde el frontend) | 51 passed, 0 failed |
| CORS | Se añadieron orígenes `127.0.0.1:5173` y `127.0.0.1:8080` |

Informe E2E completo: `docs/integration-report.md`.

## EP-02 — HU_DN_01_17 (desactivar usuario)

- Endpoints `POST /auth/admin/users/{id}/deactivate`, validaciones de autodesactivación y Gerente con proyectos.
- Revocado inmediato vía `SessionRepository.revoke_all_active_for_user`.
- Tests: `tests/api/test_user_lifecycle_api.py`.

## EP-02 — HU_DN_01_18 (reactivar usuario)

- Endpoint `POST /auth/admin/users/{id}/reactivate`, error `REACTIVATE_NOT_INACTIVE` si ya está activo.

## EP-02 — HU_DN_01_19 (tareas pendientes)

- `GET /auth/admin/users/{id}/pending-assignments` y adaptador `pending_assignments_query`.

## EP-02 — HU_DN_01_21 (perfil y avatar)

- Rutas `profile_routes`, migración `004_user_avatar`, almacenamiento local validado (PNG/JPG/WEBP ≤ 2 MB).
- Dependencia `python-multipart` para `PATCH` multipart.

## Despliegue Supabase

- Migraciones aplicadas con `DATABASE_URL` + `sslmode=require`; seed vía `python -m app.cli.seed` y variables `SEED_*` (ver `docs/deployment-guide.md`).

## EP-03 — Proyectos (rama `feature/ep-03-projects-pro`)

| HU | Backend | Tests |
|---|---|---|
| HU_DN_02_22 | `CreateProjectUseCase`, estado inicial `planificacion`, RN-AUT-03 | `test_hu_22_*` |
| HU_DN_02_23 | `UpdateProjectUseCase`, admin o gerente responsable | `test_hu_23_*` |
| HU_DN_02_24 | `UpdateProjectStatusUseCase`, valores SRS | `test_hu_24_*` |
| HU_DN_02_25 | `AssignProjectManagerUseCase`, gerente activo | `test_hu_25_*` |
| HU_DN_02_26 | `DeleteProjectUseCase`, soft delete + `audit_logs` | `test_hu_26_*` |

Validación local: `pytest` 256 passed, cobertura ~89 %, `ruff check` limpio, import-linter BR-4 cumplido (`project_routes` en orchestration).

## EP-04 / EP-05 — Disponibilidad y Reuniones (ramas `feature/ep-04-availability-dis`, `feature/ep-05-meetings-age`)

| HU | Backend | Tests |
|---|---|---|
| HU_DN_02_32 | `SaveUserAvailabilityUseCase`, `GetUserAvailabilityUseCase`, `SqlAlchemyAvailabilityRepository`, migración `006_availability_and_meetings.py` | `test_save_user_availability_success_and_no_changes`, `test_availability_mine_save_and_retrieve_and_no_changes` |
| HU_DN_02_33 | Reutilización/herencia con fallback a última disponibilidad guardada (`is_inherited: true`) | `test_get_user_availability_inheritance` |
| HU_DN_02_34 | `GetTeamAvailabilityUseCase`, `TeamMembersLookup` (BR-4), control de acceso solo admin/manager | `test_get_team_availability_permissions`, `test_availability_team_permissions` |
| HU_DN_03_35 | Reglas de validación de criterios en dominio: intervalo 24h, días obligatorios, participantes obligatorios, duración en horas completas | `test_validate_meeting_search_criteria` |
| HU_DN_03_36 | `SearchMeetingSlotsUseCase` (cálculo de intersección y exclusión de reuniones agendadas), `CreateMeetingUseCase`, `MeetingModel`, `MeetingParticipantModel` | `test_search_meeting_slots_and_create_meeting`, `test_search_meeting_slots_no_slots_found` |

Validación local:
- `pytest -m "not integration"`: 277 pruebas pasadas, 0 fallos.
- Cobertura: 89 % total en `app/` (umbral mínimo 80 %).
- Calidad de código: `ruff check .` limpio, `ruff format --check .` limpio.
- Verificación estática de tipos: `mypy .` limpio (0 errores en 170 archivos).
- Arquitectura modular: `lint-imports` limpio (3 contratos cumplidos: BR-1, BR-2, BR-4).


