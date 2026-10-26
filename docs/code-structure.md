# Estructura de código (backend) — cambios de EP-01

Arquitectura hexagonal por módulos, verificada con `import-linter` (BR-1 API sin acceso a ORM, BR-2 dominio puro,
BR-4 módulos independientes incluso de forma transitiva).

```
app/
  main.py                      Composición: handlers de error, middleware, routers, autenticador de sesión
  config.py                    Settings (solo variables de entorno, fail-fast, perfil de producción endurecido)
  cli/seed.py                  Usuarios locales desde SEED_* (bloqueado en producción)
  modules/auth/
    domain/                    entities (User, UserSession, LoginAttempt), rules, messages, errors, ports
    application/               use_cases (RegisterManager), session_use_cases (Login, Logout, AuthenticateSession),
                               dtos, mappers
    infrastructure/            models (users, sessions, login_attempts), repositories, session_tokens
    api/routes.py              /register /login /logout /session
  orchestration/
    auth_container.py          Cableado de casos de uso del módulo auth
    security.py                get_current_user/get_current_session (cookie) sin importar el módulo auth
    error_handling.py          Contrato de error único; sin eco de valores ni internos
    middleware.py              Cabeceras de seguridad + validación de Origin (CSRF)
  shared/
    domain/errors.py           AppError / ErrorKind
    application/identity.py    CurrentUser, CurrentSession
    infrastructure/            hasher (Argon2id con parámetros de entorno), types.UtcDateTime, database
migrations/versions/           001 esquema inicial, 002 sesiones e intentos de acceso
scripts/                       generate_env.py, scan_secrets.py
tests/
  unit/ application/ api/ integration/   fakes.py, support.py, conftest.py (fixtures SQLite y PostgreSQL)
```

## Dependencias entre capas relevantes

- `security.py` no conoce `auth`: `app.main` registra la fábrica del autenticador. Así los módulos
  `projects`, `tasks` y `notifications` solo dependen de `CurrentUser` (BR-4).
- Los casos de uso reciben puertos (`Clock`, `IdGenerator`, `PasswordHasher`, repositorios, `UnitOfWork`),
  por lo que se prueban con dobles en memoria (`tests/fakes.py`).

## Archivos retirados

`app/modules/auth/infrastructure/token_service.py` y la dependencia `pyjwt` (reemplazados por sesiones de servidor).

## EP-03 — Proyectos (HU_DN_02_22 … HU_DN_02_26)

```
app/modules/projects/
  domain/          entities (prioridad, estado), messages (literales HU), rules, ports (+ ManagerLookup)
  application/     use_cases (crear, editar, estado, gerente, soft delete), access.py, mappers.py, dtos.py
  infrastructure/  models (projects + deleted_at), repositories (cascada lógica tareas)
  api/routes.py    stub documental; HTTP real en orchestration
app/orchestration/
  project_routes.py           POST/PATCH/DELETE /api/v1/projects…
  project_manager_lookup.py   puerto ManagerLookup → repositorio auth (sin importar módulo auth desde projects)
  projects_container.py       fábricas de casos de uso
migrations/versions/005_project_ep03_fields.py
tests/api/test_projects_ep03_api.py
```

`GET /api/v1/auth/managers` lista gerentes activos para formularios (auth module).

## EP-04 / EP-05 — Disponibilidad y Reuniones (HU_DN_02_32 … HU_DN_02_34, HU_DN_03_35 … HU_DN_03_41)

```
app/modules/availability/
  domain/          entities (TimeSlot, UserAvailability, Meeting, MeetingParticipant, VALID_MEETING_TYPES, VALID_PARTICIPANT_RESPONSES), rules, messages, ports (AvailabilityRepository, TeamMembersLookup, ProjectLookup, NotificationSender, UserLookup)
  application/     use_cases (SaveUserAvailability, GetUserAvailability, GetTeamAvailability, SearchMeetingSlots, CreateMeeting, ListMeetings, GetMeetingDetail, CancelMeeting, RespondMeeting, UpdateMeetingSummary), dtos.py
  infrastructure/  models (user_availabilities, meetings [type, summary, minutes_url], meeting_participants [response]), repositories (SqlAlchemyAvailabilityRepository)
app/orchestration/
  availability_routes.py     POST/GET /api/v1/availability/mine, GET /availability/team, POST /availability/search-slots, POST/GET /availability/meetings, GET /availability/meetings/{id}, POST /availability/meetings/{id}/cancel, POST /availability/meetings/{id}/respond, POST /availability/meetings/{id}/summary, GET /availability/projects
  team_members_lookup.py     puerto TeamMembersLookup → resuelve usuarios visibles por rol (BR-4)
  meeting_adapters.py        puertos ProjectLookup, UserLookup, NotificationSender (BR-4)
migrations/versions/
  006_availability_and_meetings.py
  007_meeting_fields_and_responses.py
tests/
  unit/test_availability_domain.py
  application/test_availability_use_cases.py
  api/test_availability_api.py
  api/test_meetings_ep05_api.py
```

## EP-06 — Backlog TAR (HU_DN_04_47 … HU_DN_04_55)

```
app/modules/backlog/
  domain/          entities (Epic, UserStory, StoryTask), messages (literales HU), rules, ports (BacklogRepository)
  application/     access.py (ProjectContext ports), use_cases (CRUD épica/HU/tarea, Fibonacci, horas, asignación)
  infrastructure/  models (epics, user_stories, story_tasks), repositories
app/orchestration/
  backlog_routes.py      GET /projects/{id}/backlog, POST epics, PATCH epics, user-stories, story-points, story-tasks
  backlog_adapters.py      ProjectLookup + ActiveMemberLookup (BR-4)
migrations/versions/009_ep06_backlog_tar.py
migrations/versions/010_ep06_time_status_invites.py
tests/api/test_backlog_api.py
tests/unit/test_backlog_rules.py
```

HU_DN_04_56–61: `task_time_logs`, `task_status_history`, `logged_hours`, `POST /projects/{id}/tasks/{taskId}/time-logs`, `PATCH .../status`, `GET /projects/{id}/backlog/tree`, `GET /users/me/tasks`.

Invitación de desarrollador: `users.invitation_status`, código hasheado, `POST /auth/invitations/decision`, `POST /auth/invitations/activate`, renovación y borrado administrativo. El API no devuelve contraseñas.

## EP-07 — Sprints SPR (HU_DN_05_63 … HU_DN_05_67)

```
app/modules/sprints/
  domain/          Sprint, SprintStatus, messages, rules, SprintRepository port
  application/     access (admin/manager), metrics (puntos y progreso), use_cases
  infrastructure/  SprintModel, SqlAlchemySprintRepository
app/orchestration/sprint_routes.py
  POST   /projects/{id}/sprints
  GET    /projects/{id}/sprints
  GET    /projects/{id}/sprints/current
  POST   /projects/{id}/sprints/{sprintId}/start
  PATCH  /projects/{id}/user-stories/{storyId}/sprint
migrations/versions/012_ep07_sprints.py   (índice único ACTIVE por proyecto)
tests/api/test_sprints_api.py
tests/unit/test_sprint_rules.py
```

## EP-07 — Sprints SPR (HU_DN_05_68 … HU_DN_05_71)

```
app/modules/sprints/application/burndown.py     líneas ideal/real por día
app/modules/backlog/infrastructure/repositories.py
  latest_done_date_by_task(project_id)            histórico DONE por tarea
app/orchestration/sprint_routes.py
  GET    /projects/{id}/sprints/history
  GET    /projects/{id}/sprints/{sprintId}/burndown
  POST   /projects/{id}/sprints/{sprintId}/close
migrations/versions/013_ep07_sprint_closed_at.py
app/modules/sprints/infrastructure/models.py    índice parcial unique_active_sprint_per_project (ORM)
tests/unit/test_burndown.py
tests/api/test_sprints_api.py                   HU 68–71
```

Cierre (`CLOSED` + `closed_at`): historias incompletas → backlog (`sprint_id` NULL) o sprint planificado; sprint cerrado inmutable para asignaciones.

