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

---

## EP-05 — Agendamiento y Reuniones (HU_DN_03_37 … HU_DN_03_41)

### Análisis del Orquestador (Modo Lote / Épica)
- **Fecha:** 2026-10-13
- **Clasificación del lote:** FULL_STACK
- **Complejidad:** MODERATE / COMPLEX (Score: 82/100)
- **Políticas cargadas:** `policies.xml`, `adaptive-policies.xml`, `project-modes.xml`, `engineering-standards.xml` (seguridad, mensajes_literales, contrato_de_error, quality_gates, estrategia_de_pruebas, accesibilidad).
- **Project Mode:** EXTEND_EXISTING en ambos repositorios.
- **Ramas:** `feature/ep-05-meetings-age` (tanto backend como frontend).
- **Prohibición de push:** No publicar ramas hasta verificación integral completa.

#### Grafo de dependencias y flujo:
1. `HU_DN_03_37`: Selección de horario disponible resultante de búsqueda (HU_DN_03_36) y apertura modal de confirmación en solo lectura (fecha, hora, duración, participantes).
2. `HU_DN_03_38`: Programación de reunión desde ventana de confirmación (título ≤ 100 caracteres obligatorio, tipo obligatorio entre Daily/Planning/Review/Retro/General, proyecto asociado obligatorio con validación de membresía de todos los participantes y prellenado de enlace sugerido, enlace opcional con formato URL válido, rechazo de solapamiento concurrente para cualquier participante, persistencia, notificación a participantes y redirección a reuniones).
3. `HU_DN_03_39`: Listado de reuniones (Próximas y Pasadas) con alcance por rol (Admin: todas; Gerente: propias y de sus proyectos; Desarrollador: solo participante), orden cronológico (próximas asc; pasadas sep), datos completos y estados.
4. `HU_DN_03_40`: Vista calendario interactiva con conmutador Lista/Calendario con el mismo conjunto de reuniones, título y tipo distinguibles.
5. `HU_DN_03_41`: Detalle de reunión desde lista o calendario, participantes y sus respuestas (pendiente, aceptada, rechazada), resumen y acta, acciones según rol ('Enviar a Google Calendar', 'Aceptar / Rechazar', 'Cancelar reunión', 'Registrar resumen y acta'), control de acceso por rol (Desarrollador denegado si no participa).

#### Contrato Compartido:
- **API Endpoints:**
  - `POST /api/v1/availability/meetings`: Creación de reunión con campos `title`, `type`, `project_id`, `date`, `start_time`, `end_time`, `duration`, `link`, `participant_ids`.
  - `GET /api/v1/availability/meetings`: Listado de reuniones filtradas por alcance de rol y parámetros opcionales.
  - `GET /api/v1/availability/meetings/{id}`: Detalle completo de reunión con creador, participantes y respuestas.
  - `POST /api/v1/availability/meetings/{id}/cancel`: Cancelación de reunión por creador.
  - `POST /api/v1/availability/meetings/{id}/respond`: Registro de respuesta de participante ('aceptada' | 'rechazada').
  - `POST /api/v1/availability/meetings/{id}/summary`: Registro de resumen (≤ 2000 chars) y URL de acta.
- **Mensajes Literales Verbatim:**
  - Título vacío: `'El título de la reunión es obligatorio.'`
  - Tipo vacío: `'Seleccione el tipo de reunión.'`
  - Enlace inválido: `'El enlace de la reunión no tiene un formato de URL válido.'`
  - Proyecto vacío: `'Debe seleccionar un proyecto.'`
  - Miembros no pertenecientes al proyecto: `'Todos los participantes deben ser miembros del proyecto seleccionado.'`
  - Solapamiento concurrente: `'Uno o más participantes ya tienen una reunión en ese horario.'`
  - Éxito al programar: `'Reunión programada correctamente.'`
  - Éxito sin datos: `'No hay reuniones para mostrar.'`
  - Fallo técnico genérico: `'No fue posible completar la operación. Intente nuevamente.'`
  - Fallo de carga: `'No fue posible cargar la información. Intente nuevamente.'`
  - Acceso denegado: `'Acceso denegado. No tiene permisos para realizar esta acción.'`### Implementación Backend (EP-05)

#### Componentes Desarrollados:
1. **Entidades y Dominio (`app/modules/availability/domain/`):**
   - Mensajes literales verbatim en `messages.py`: `MEETING_TITLE_REQUIRED`, `MEETING_TYPE_REQUIRED`, `PROJECT_REQUIRED`, `PARTICIPANTS_MUST_BE_PROJECT_MEMBERS`, `INVALID_MEETING_LINK`, `PARTICIPANT_MEETING_CONFLICT`, `NO_MEETINGS_TO_SHOW`, `MEETING_CANCELLED`, `MEETING_RESPONSE_REGISTERED`, `MEETING_SUMMARY_REGISTERED`.
   - `Meeting` entity extendida con `type`, `summary`, `minutes_url`, validaciones de tipo de reunión (`VALID_MEETING_TYPES`) y respuestas (`VALID_PARTICIPANT_RESPONSES`).
   - Puertos de dominio en `ports.py`: `ProjectLookup`, `NotificationSender`, `UserLookup`, y extensiones a `AvailabilityRepository`.
   - Reglas de negocio: detección de solapamiento concurrente en `check_concurrent_meeting`, y alcance de consulta por rol.

2. **Infraestructura y Persistencia (`app/modules/availability/infrastructure/`):**
   - Migración Alembic `007_meeting_fields_and_responses.py` añadiendo columnas `type`, `summary`, `minutes_url` a `meetings` y `response` a `meeting_participants`.
   - Modelos SQLAlchemy y repositorio `SqlAlchemyAvailabilityRepository` implementando consultas de rol, actualización de respuestas de participantes, y verificación de concurrencia.
   - Adaptadores en `app/orchestration/meeting_adapters.py` para cumplir aislamiento modular (BR-4) y estándares de reloj/id (TID251 / HC-09).

3. **Casos de Uso y API (`app/modules/availability/application/` y `app/orchestration/`):**
   - `CreateMeetingUseCase`: validaciones de título, tipo, proyecto, membresía de participantes, URL de enlace, detección de concurrencia (HTTP 409 `PARTICIPANT_MEETING_CONFLICT`), persistencia atómica con `UnitOfWork` y despacho de notificaciones a participantes.
   - `ListMeetingsUseCase`: filtrado según rol (Admin: todas; Manager: propias y de proyectos gestionados; Developer: solo participante) y parámetros de fecha y estado (`proximas` / `pasadas`).
   - `GetMeetingDetailUseCase`: detalle enriquecido con participantes y sus respuestas; control estricto de acceso (403 para desarrolladores no participantes).
   - `CancelMeetingUseCase`: cancelación exclusiva por creador o admin.
   - `RespondMeetingUseCase`: registro de respuesta `aceptada` o `rechazada` por el participante.
   - `UpdateMeetingSummaryUseCase`: registro de resumen (máx 2000 caracteres) y URL de acta por creador/admin, marcando estado como `completed`.
   - `availability_routes.py`: rutas REST completas con serialización Pydantic.

#### Verificación de Quality Gates Backend:
- `pytest`: 290 pruebas unitarias y de integración ejecutadas y aprobadas (100% de éxito).
- Pruebas dedicadas EP-05: `tests/api/test_meetings_ep05_api.py` (13 pruebas API cubriendo todas las HUs y casos extremos).
- `ruff check .`: 0 errores.
- `ruff format --check .`: 191 archivos formateados correctamente.
- `mypy app/`: 0 errores en 122 archivos.
- `lint-imports`: 3 contratos cumplidos (BR-1, BR-2, BR-4 intactos).
- `scan_secrets.py`: 0 secretos detectados (205 archivos limpios).
- `alembic upgrade head`: Migración 007 aplicada exitosamente.

---

## Implementación y Evaluación Exhaustiva de HU_DN_03_42, HU_DN_03_44, HU_DN_03_45 y HU_DN_03_46

### 1. HU_DN_03_42 — Enviar reunión a Google Calendar y Fallback
- **Backend:** `GetMeetingDetailUseCase` y `_build_meeting_dto` exponen metadatos completos requeridos para la integración externa: título, fechas/horas de inicio y fin, duración, enlace, proyecto, y lista de participantes con emails para prellenado (`&add=...`).
- **Control de acceso:** Creador, participantes y Administradores autorizados; desarrolladores ajenos reciben HTTP 403 `ACCESS_DENIED`.
- **Frontend:** Construcción de URL con invitados (`buildGoogleCalendarUrl`), detección de popup blocker (`window.open`), mensaje literal `No fue posible abrir Google Calendar. Puede copiar los datos de la reunión.`, botón de fallback «Copiar datos de la reunión» con `formatMeetingCopyData`, toast `Datos de la reunión copiados.` y manejo de fallo de portapapeles `No fue posible copiar los datos. Cópielos manualmente.`.

### 2. HU_DN_03_44 — Responder convocatoria de reunión
- **Backend:** `RespondMeetingUseCase` (`POST /api/v1/availability/meetings/{id}/respond`):
  - Acepta respuestas `'aceptada'` y `'rechazada'`.
  - Restricción: Si la reunión fue cancelada, rechaza con HTTP 400 `MEETING_CANCELLED` y mensaje literal `"La reunión fue cancelada; no es posible responder."`.
  - Restricción: Si la reunión ya fue realizada (fecha u hora pasada), rechaza con HTTP 400 `MEETING_ALREADY_PAST` y mensaje literal `"No es posible responder una reunión ya realizada."`.
  - Usuarios no convocados reciben HTTP 403.
- **Frontend:** Acciones «Aceptar» y «Rechazar» en el detalle, ocultas reactivamente si la reunión ya ocurrió o fue cancelada; mapeo de errores del backend a toasts.

### 3. HU_DN_03_45 — Cancelar reunión programada y RN-AGE-05
- **Backend:** `CancelMeetingUseCase` (`POST /api/v1/availability/meetings/{id}/cancel`):
  - **RN-AGE-05:** Solo el creador de la reunión puede cancelarla (`meeting.creator_id == actor.id`). Administradores u otros usuarios reciben HTTP 403 `ONLY_CREATOR_CAN_CANCEL` con mensaje literal `"Solo el creador de la reunión puede cancelarla."`.
  - Despacho atómico de notificaciones a todos los participantes con tipo `meeting_cancelled` vía `SqlAlchemyMeetingNotificationSender`.
  - Estado pasa a `cancelled` y se excluye del filtro `filter_type=upcoming`.
- **Frontend:** Modal de confirmación con mensaje literal `"¿Está seguro de que desea cancelar esta reunión? Se notificará a los participantes."`, botones `"Confirmar"` y `"Cancelar"`. El botón de cancelar solo es visible para el creador.

### 4. HU_DN_03_46 — Registrar resumen y acta de reunión
- **Backend:** `UpdateMeetingSummaryUseCase` (`POST /api/v1/availability/meetings/{id}/summary`):
  - Restricción: Solo reuniones realizadas (estado `completed` o con hora fin ya transcurrida automáticamente). Si se intenta en reunión futura/programada, rechaza con HTTP 400 `MEETING_NOT_COMPLETED` y `"Solo se puede registrar resumen y acta en reuniones realizadas."`.
  - Validación de resumen obligatorio: HTTP 400 `SUMMARY_REQUIRED` con `"El resumen es obligatorio."`.
  - Validación de longitud máxima: Si supera 2000 caracteres, HTTP 400 `SUMMARY_TOO_LONG` con `"El resumen no puede superar 2000 caracteres."`.
  - Validación de formato URL: HTTP 400 `INVALID_MINUTES_URL` con `"La URL del acta no tiene un formato válido."`.
  - Creador o Administrador pueden registrar o editar; los datos quedan visibles para todos los participantes.
- **Frontend:** Modal con validación en tiempo real y contador de caracteres (0/2000), toast de confirmación `"Resumen y acta guardados correctamente."`.

---

## EP-06 — Backlog TAR (HU_DN_04_47 … HU_DN_04_55)

**Estado:** COMPLETED (implementación) | **Pruebas locales:** NOT_RUN (venv/docker sin `.env` generado en agente)

### Backend
- Módulo `app/modules/backlog`, migración `009_ep06_backlog_tar`, rutas `orchestration/backlog_routes.py`.
- Casos de uso con permisos Admin/Gerente (épica, HU, puntos) y miembros del proyecto (tareas, horas, asignación).
- Tests: `tests/api/test_backlog_api.py`, `tests/unit/test_backlog_rules.py`.

## EP-06 — HU_DN_04_56 … HU_DN_04_61

**Estado:** COMPLETED
**Fecha:** 2026-10-20
**Evidencia:** `pytest tests/ --ignore=tests/integration` → 306 passed. `ruff check .` limpio.

- Horas: suma en la misma transacción que `task_time_logs`.
- Estado: historial en `task_status_history`; Corrección rechazada en cambios manuales.
- Gerente con tareas asignadas sigue creando épicas (HU_DN_04_58).
- Árbol filtra en memoria con parámetros; el desarrollador solo recibe sus tareas.
- Invitación: contraseña aleatoria no reusable, código Argon2, enlace de un solo uso, vigencia 24 h, máximo 3 renovaciones, rechazo visible y borrado a los 3 días.

---

## EP-07 — Sprints SPR (HU_DN_05_68 … HU_DN_05_71)

**Estado:** COMPLETED | **Rama:** `feature/ep-07-sprints`

### HU_DN_05_68 — Burndown
- `app/modules/sprints/application/burndown.py`: línea ideal (lineal) y real (puntos restantes por día según cierre DONE en tareas).
- `latest_done_date_by_task` en backlog (histórico `task_status_history`).
- `GET /projects/{id}/sprints/{sprintId}/burndown` → `{ ideal_line, actual_line }`.
- Tests: `tests/unit/test_burndown.py`, `tests/api/test_sprints_api.py::test_hu_68_burndown_chart`.

### HU_DN_05_69 / HU_DN_05_70 — Cierre y reubicación
- `CloseSprintUseCase`: solo sprint `ACTIVE`; `closed_at`; estado `CLOSED`.
- Payload: `incomplete_stories_destination: BACKLOG` o `incomplete_stories_action: MOVE_TO_SPRINT` + `target_sprint_id`.
- Inmutabilidad: asignación rechazada en sprints `CLOSED` (403).
- Tests: cierre con backlog, inmutabilidad post-cierre.

### HU_DN_05_71 — Historial
- `GET /projects/{id}/sprints/history` (ruta antes de `{sprint_id}`): sprints `CLOSED` ordenados por `end_date` desc, puntos comprometidos/completados y % cumplimiento.
- Test: `test_hu_71_sprint_history`.

### Fix esquema (CI)
- Índice parcial `unique_active_sprint_per_project` declarado en ORM (`postgresql_where` / `sqlite_where`) alineado con migración 012.
- Migración `013_ep07_sprint_closed_at.py`.

**Evidencia:** `pytest` 316+ passed (SQLite/API); `test_migrated_schema_matches_orm_models` OK con Postgres local (Docker 5434).


