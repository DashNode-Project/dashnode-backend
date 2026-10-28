# Reporte de integración — EP-01 Autenticación y sesiones

**Fecha de validación:** 2026-10-11  
**Pila:** `dashnode-backend` (API + PostgreSQL 16) y `dashnode-frontend` (nginx + SPA)  
**Ramas:** `feature/ep-01-auth-sessions` en ambos repositorios  
**Directorio intocable:** `demo/` (sin cambios)

Este informe es idéntico en backend y frontend.

## Cómo se levantó la pila

```bash
# backend
python scripts/generate_env.py
docker compose up -d --build
python -m app.cli.seed

# frontend
copy .env.example .env
docker compose up -d --build
```

Puertos: API `127.0.0.1:8000`, Postgres `127.0.0.1:5434`, web `127.0.0.1:8080`.
Red Docker: `dashnode-net` (alias `dashnode-api`).

Salud verificada: `dashnode-backend-api-1` healthy, `dashnode-backend-db-1` healthy,
`dashnode-web` healthy. El frontend alcanza `/api/v1` por el mismo origen.

## Contrato de integración

| Método | Ruta | Auth | Éxito | Errores literales |
|---|---|---|---|---|
| POST | `/api/v1/auth/register` | público | 201 + mensaje de registro | 400/403/409/500 |
| POST | `/api/v1/auth/login` | público | 200 + cookie HttpOnly | 400/401/403/429/500 |
| POST | `/api/v1/auth/logout` | cookie | 200 + «Sesión cerrada correctamente.» | 500 |
| GET | `/api/v1/auth/session` | cookie | 200 `{user, expires_at}` | 401 expirada / no autenticado |

Cookie: `dashnode_session`, `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age` = 8 h + retención.
El token no viaja en el cuerpo ni en JS. CSRF: Origin debe estar en `CORS_ORIGINS`.
Contrato de error: `{ "error": { "code", "message", "fields" } }`.

## Flujo E2E

1. Visitante abre `/` (sin sesión, sin datos protegidos).
2. Registro de Gerente → 201 → redirección a `/iniciar-sesion`.
3. Login → cookie → `/inicio/gerente` (u otra ruta por rol).
4. Recarga → `GET /auth/session` restaura la misma vista (sin renovar TTL).
5. Cerrar sesión → cookie invalidada → login con mensaje de éxito.
6. Reutilizar la cookie previa → 401.

## Validación funcional

| Criterio | Estado | Evidencia |
|---|---|---|
| HU_01 landing pública + accesos | PASS | Navegador `http://localhost:8080/` + E2E landing 200 |
| HU_01 sin datos protegidos | PASS | Landing no llama API; E2E sin cookie |
| HU_02 validaciones y rol forzado | PASS | E2E: name/email/password/mismatch + role admin/developer → 403 |
| HU_02 éxito y unicidad | PASS | E2E 201 + 409 case-insensitive |
| HU_03 credenciales genéricas | PASS | E2E: mismo 401 para correo inexistente y contraseña incorrecta |
| HU_03 5 intentos / 15 min | PASS | E2E: sexto → 429, incluso con contraseña correcta |
| HU_03 roles admin/gerente/dev | PASS | E2E con cuentas seed |
| HU_03 cuenta desactivada | PASS | E2E 403 con contraseña correcta; 401 si es incorrecta |
| HU_03 cookie 8 h HttpOnly | PASS | E2E flags + TTL ~8.00 h |
| HU_04 logout + replay | PASS | E2E 200 + sesión previa 401 |
| HU_05 restore sin renovar | PASS | E2E `expires_at` idéntico |
| CSRF origen extraño | PASS | E2E 403 `ORIGIN_NOT_ALLOWED` |

## Validación seguridad

- AuthN/AuthZ: sesión opaca en servidor; hash Argon2id; digest SHA-256 del token.
- Sin secretos en respuestas, logs ni repositorio (`scan_secrets` limpio).
- CORS explícito; cookie no leíble por scripts.
- localStorage/sessionStorage prohibidos en el cliente (ESLint + tests).

## Validación UX y accesibilidad

- Loading / success / error / disabled en formularios.
- Errores por campo con literales de la HU.
- Skip link, labels, `aria-pressed` en mostrar contraseña, landmarks.
- Landing y formularios verificados en el navegador (campos, botón deshabilitado vacío).

## Scripts generados

| Ruta | Propósito |
|---|---|
| `dashnode-frontend/scripts/e2e-stack.mjs` | E2E HTTP mismo origen + cookie jar |
| `dashnode-frontend/scripts/scan-secrets.mjs` | Escaneo de secretos |
| `dashnode-backend/scripts/generate_env.py` | `.env` local con secretos aleatorios |
| `dashnode-backend/scripts/scan_secrets.py` | Escaneo de secretos |

```bash
node scripts/e2e-stack.mjs --base http://localhost:8080 --env-file ../dashnode-backend/.env
# 51 checks passed, 0 failed, 0 skipped
```

## Quality gates de capa (re-ejecutados en integración)

| Capa | Comando | Resultado |
|---|---|---|
| Backend | `pytest --cov=app --cov-fail-under=80` | 218 passed, cobertura 94.77 % |
| Backend | ruff / mypy --strict / import-linter / scan_secrets | Verde |
| Frontend | `npm run check` | typecheck + lint + prettier + coverage + secrets |

## Acceptance Score

- **Resultado:** 100 % de criterios integrables de HU_DN_01_01 a HU_DN_01_05
- **Estado:** APROBADO
- **Publication gate:** PASSED (suites verdes, E2E verde, sin secretos, `demo/` intacto)

## Pendientes fuera de alcance

- Recuperación de contraseña (HU_DN_01_06): enlace inerte + variables `SMTP_*` / `FRONTEND_BASE_URL` preparadas.
- Desactivación de usuarios (HU_DN_01_17): se prueba con cuenta seed.
- Demo del Product Owner (paso humano).

---

## EP-03 — Proyectos (HU_DN_02_22 … HU_DN_02_26)

**Rama:** `feature/ep-03-projects-pro` (backend + frontend).

| Método | Ruta | Roles | Mensaje de éxito (literal) |
|---|---|---|---|
| POST | `/api/v1/projects` | Admin, Gerente | Proyecto creado correctamente. |
| PATCH | `/api/v1/projects/{id}` | Admin; Gerente si responsable | Proyecto actualizado correctamente. |
| PATCH | `/api/v1/projects/{id}/status` | Admin; Gerente si responsable | Estado del proyecto actualizado. |
| POST | `/api/v1/projects/{id}/manager` | Admin; Gerente si responsable | Gerente responsable actualizado correctamente. |
| DELETE | `/api/v1/projects/{id}` | Solo Admin | Proyecto eliminado correctamente. |
| GET | `/api/v1/auth/managers` | Admin, Gerente | Lista de gerentes activos (formularios) |

Frontend: `/proyectos` (listado + crear), `/proyectos/:id` (resumen, editar, estado, gerente, eliminar admin). Notificaciones vía `ToastProvider` (10 s, inferior derecha), incluido «Funcionalidad en desarrollo».

---

## EP-04 y EP-05 — Disponibilidad y Reuniones (HU_DN_02_32 … HU_DN_02_34, HU_DN_03_35 … HU_DN_03_36)

**Ramas:** `feature/ep-04-availability-dis`, `feature/ep-05-meetings-age` (backend + frontend).

### Contrato de integración API

| Método | Ruta | Roles | Descripción / Mensaje de éxito |
|---|---|---|---|
| GET | `/api/v1/availability/mine?week=YYYY-MM-DD` | Autenticado | Consulta disponibilidad propia y marca si es heredada (`is_inherited`). |
| POST | `/api/v1/availability/mine` | Autenticado | Guarda bloques horarios en 24h (formato UTC). Éxito: «Disponibilidad guardada correctamente.». Si no hay cambios: 400 «No hay cambios por guardar.». |
| GET | `/api/v1/availability/team?week=YYYY-MM-DD` | Admin, Gerente | Rejilla semanal de disponibilidad de usuarios visibles con indicadores textuales ("D" / "ND") y visuales. Desarrollador: 403 `AccessDeniedError`. |
| POST | `/api/v1/availability/search-slots` | Admin, Gerente | Búsqueda e intersección de franjas horarias libres según criterios (intervalo, días, participantes, duración en horas completas). Excluye reuniones agendadas. Si vacío: 400 «No hay horarios disponibles para los criterios seleccionados.». |
| POST | `/api/v1/availability/meetings` | Admin, Gerente | Crea y agenda reunión. Éxito: «Reunión agendada correctamente.». |
| GET | `/api/v1/availability/meetings` | Autenticado | Lista reuniones programadas para el usuario autenticado. |

Frontend: `/disponibilidad` (pestañas «Mi disponibilidad», «Equipo», «Agendar reunión»). Integración estricta con la plantilla visual Figma en `demo/`. Notificaciones toast con mensajes literales de los criterios de aceptación.

---

## EP-05 — Agendamiento y Reuniones (HU_DN_03_37 … HU_DN_03_41)

**Ramas:** `feature/ep-05-meetings-age` (backend + frontend).  
**Rutas SPA:** `/disponibilidad` (agendamiento interactivo) y `/reuniones` (gestión integral y calendario) en `SideNav`.

### Contrato de integración API (EP-05)

| Método | Ruta | Roles | Descripción / Mensaje de éxito |
|---|---|---|---|
| POST | `/api/v1/availability/meetings` | Admin, Gerente | Programa reunión con campos `title`, `type`, `project_id`, `date`, `start_time`, `end_time`, `duration`, `link`, `participant_ids`. Valida membresía de proyecto, solapamiento concurrente y emite notificaciones atómicas. Éxito: «Reunión programada correctamente.». |
| GET | `/api/v1/availability/meetings` | Autenticado | Lista reuniones con alcance por rol (Admin: todas; Gerente: propias y de sus proyectos; Desarrollador: participante). Soporta `filter_type=proximas|pasadas` y filtros de fecha. Éxito: lista de reuniones o «No hay reuniones para mostrar.». |
| GET | `/api/v1/availability/meetings/{id}` | Autenticado (Involucrado) | Detalle completo de reunión con creador, participantes y estado de respuesta (`pendiente`, `aceptada`, `rechazada`), acuerdos y acta. Desarrollador ajeno: 403 «Acceso denegado. No participa en esta reunión.». |
| POST | `/api/v1/availability/meetings/{id}/cancel` | Creador, Admin | Cancela reunión programada. Actualiza estado a `cancelled` y notifica participantes. Éxito: «Reunión cancelada correctamente.». |
| POST | `/api/v1/availability/meetings/{id}/respond` | Participante | Registra respuesta (`aceptada` o `rechazada`) del usuario convocado. Éxito: «Respuesta registrada correctamente.». |
| POST | `/api/v1/availability/meetings/{id}/summary` | Creador, Admin | Registra o actualiza resumen de acuerdos (≤ 2000 caracteres) y URL de acta. Éxito: «Resumen y acta registrados correctamente.». |
| GET | `/api/v1/availability/projects` | Admin, Gerente | Lista proyectos gestionados con enlace de videoconferencia predeterminado para prellenado automático. |

### Resultados de Calidad y Verificación

| Capa | Control | Resultado | Estado |
|---|---|---|---|
| Backend | `pytest` | 290 tests pasados (100 % pass rate; 13 en suite EP-05) | APROBADO |
| Backend | `ruff check .` & `ruff format --check` | 0 advertencias, 0 errores, 100% formateado | APROBADO |
| Backend | `mypy app/` | 0 errores en 122 archivos fuente | APROBADO |
| Backend | `lint-imports` | 3 contratos de arquitectura limpios | APROBADO |
| Backend | `scan_secrets.py` | 0 secretos detectados | APROBADO |
| Frontend | `tsc --noEmit` (`npm run typecheck`) | 0 errores de tipos | APROBADO |
| Frontend | `eslint .` (`npm run lint`) | 0 errores, 0 advertencias | APROBADO |
| Frontend | `prettier --check .` | 100 % código formateado | APROBADO |
| Frontend | `vitest run` | 269 tests pasados (35 suites; 20 en MeetingsPage) | APROBADO |
| Frontend | `scan-secrets.mjs` | 0 secretos en 142 archivos | APROBADO |
| Frontend | `vite build` (`npm run build`) | Bundle de producción generado limpiamente | APROBADO |

### Matriz de Trazabilidad HU_DN_03_42 … HU_DN_03_46

| Historia de Usuario | Endpoint / Componente | Reglas y Restricciones Verificadas | Test Backend / Frontend |
|---|---|---|---|
| **HU_DN_03_42** (Google Calendar) | `GET /meetings/{id}` / `MeetingsPage.tsx` | Exportación con título, fechas, duración, link e emails invitados (`&add=...`). Fallback ante popup blocked (`googleCalendarOpenFailed`) y botón «Copiar datos de la reunión» (`formatMeetingCopyData`). | `test_hu_42_meeting_detail_and_google_calendar_data` / `MeetingsPage.test.tsx` (HU_DN_03_42) |
| **HU_DN_03_44** (Responder Convocatoria) | `POST /meetings/{id}/respond` / `MeetingsPage.tsx` | Aceptar y rechazar invitación. Rechazo de reuniones canceladas (`MEETING_CANCELLED`) y ya realizadas (`MEETING_ALREADY_PAST`). Restricción de 403 a no invitados. | `test_hu_44_respond_meeting_lifecycle_and_constraints` / `MeetingsPage.test.tsx` (HU_DN_03_44) |
| **HU_DN_03_45** (Cancelar Reunión) | `POST /meetings/{id}/cancel` / `MeetingsPage.tsx` | RN-AGE-05: Solo el creador puede cancelar (Admin recibe 403 `ONLY_CREATOR_CAN_CANCEL`). Modal con texto literal `"¿Está seguro de que desea cancelar esta reunión? Se notificará a los participantes."` y botones `"Confirmar"` / `"Cancelar"`. Notificaciones emitidas (`meeting_cancelled`). | `test_hu_45_cancel_meeting_and_notifications_and_rn_age_05` / `MeetingsPage.test.tsx` (HU_DN_03_45) |
| **HU_DN_03_46** (Resumen y Acta) | `POST /meetings/{id}/summary` / `MeetingsPage.tsx` | Solo reuniones realizadas (400 `MEETING_NOT_COMPLETED` si futura). Resumen obligatorio (`SUMMARY_REQUIRED`), máx. 2000 caracteres (`SUMMARY_TOO_LONG`), URL válida (`INVALID_MINUTES_URL`). Éxito `meetingSummarySaved`. Creador y Admin autorizados. | `test_hu_46_meeting_summary_validations_and_lifecycle` / `MeetingsPage.test.tsx` (HU_DN_03_46) |

- **Acceptance Score Final:** 100 %
- **Directorio `demo/`:** Preservado íntegramente sin modificaciones.
- **Git Commit / Push:** Omitidos estrictamente conforme a las restricciones de la solicitud.

---

## EP-06 — Backlog TAR (HU_DN_04_47 … HU_DN_04_55)

Integración verificada mediante `tests/api/test_backlog_api.py` (permisos, literales, Fibonacci, asignación a miembros, horas). Frontend consume los mismos endpoints en `ProjectBacklogTab`.

## HU_DN_04_56 … HU_DN_04_61

Login local verificado (HTTP 200) contra Postgres de Docker después de que el host remoto no resolvía DNS. SMTP: sesión autenticada (`smtp_ok`) sin enviar un mensaje de prueba. El front usa el proxy `/api` hacia `127.0.0.1:8000`.

---

## EP-07 — Sprints SPR (HU_DN_05_68 … HU_DN_05_71)

| HU | Método | Ruta | UI |
|---|---|---|---|
| HU_DN_05_68 | GET | `/projects/{id}/sprints/{sprintId}/burndown` | `SprintBurndownChart` en pestaña Sprints |
| HU_DN_05_69–70 | POST | `/projects/{id}/sprints/{sprintId}/close` | Modal «Finalizar sprint» + destino incompletas |
| HU_DN_05_71 | GET | `/projects/{id}/sprints/history` | Sección «Historial de sprints» (colapsable) |

Mensajes literales: éxito cierre `Sprint finalizado correctamente.`; historial vacío `No hay sprints finalizados en este proyecto.`; fallo técnico vía `MESSAGES.loadFailure` / `MESSAGES.technicalFailure` en frontend.

**Verificación:** `tests/api/test_sprints_api.py` (burndown, close, history); frontend `npm run check` (285 tests Vitest, `fileParallelism: false` por estabilidad de mocks compartidos).

---

## EP-08 — Tablero Kanban (HU_DN_05_72 … HU_DN_05_76)

**Fecha de validación:** 2026-10-28  
**Ramas:** `feature/ep-08-kanban-kan` (ambos repositorios)  
**Directorio intocable:** `demo/` (preservado sin modificaciones)

### Contrato de Integración y Endpoints

| Método | Ruta | Rol | Propósito | Códigos / Mensajes |
|---|---|---|---|---|
| `GET` | `/api/v1/projects/{project_id}/kanban` | Auth (Admin, Gerente, Dev) | Obtener tablero del sprint activo con 6 columnas estándar y tareas | 200 OK (`KanbanBoardResponse`); vacío si no hay sprint: `'No hay ningún sprint activo en este proyecto.'` |
| `PUT` | `/api/v1/projects/{project_id}/kanban/columns/{column_id}/wip` | Admin, Gerente | Configurar o reiniciar límite WIP por columna | 200 OK: `'Límite WIP actualizado correctamente.'`; 403 Forbidden para Dev; 400/422 límite < 1 |
| `PATCH` | `/api/v1/projects/{project_id}/tasks/{task_id}/status` | Auth (Dev sus tareas, Admin/Gerente) | Mover tarjeta entre columnas / cambiar estado de tarea | 200 OK: `'Estado de la tarea actualizado.'`; 403 Dev ajena: `'Solo puede cambiar el estado de sus propias tareas.'`; 400 Corrección manual: `'El estado Corrección solo cambia al reportar o resolver un fix.'` |
| `PATCH` | `/api/v1/projects/{project_id}/tasks/{task_id}/block` | Auth (Admin, Gerente, Dev) | Marcar o resolver impedimento o dependencia predecesora | 200 OK: `'Estado de bloqueo actualizado.'` |

### Matriz de Trazabilidad y Verificación E2E

| Historia de Usuario | Frontend | Backend | Reglas y Criterios Verificados |
|---|---|---|---|
| **HU_DN_05_72** | `ProjectKanbanTab.tsx`, `KanbanCard.tsx` | `GetKanbanBoardUseCase`, `GET /projects/{id}/kanban` | 6 columnas estándar (`TODO`, `IN_PROGRESS`, `CODE_REVIEW`, `TESTING`, `CORRECTION`, `DONE`). Tarjeta con título, tipo, avatar, HU padre y horas trabajadas vs estimadas con barra de progreso. Desarrollador solo ve sus tareas asignadas; Admin/Gerente ven todas. Mensaje si no hay sprint activo: `'No hay ningún sprint activo en este proyecto.'`. Fallo técnico: `'No fue posible cargar la información. Intente nuevamente.'`. |
| **HU_DN_05_73** | Drag & drop HTML5, selector "Mover a...", rollback visual | `ChangeStoryTaskStatusUseCase`, `PATCH /projects/{id}/tasks/{id}/status` | Arrastre y menú "Mover a...". Desarrollador restringido a sus tareas (`'Solo puede cambiar el estado de sus propias tareas.'`). Prohibición manual a/desde `CORRECTION` (`'El estado Corrección solo cambia al reportar o resolver un fix.'`). Éxito: `'Estado de la tarea actualizado.'`. Rollback visual automático ante rechazo de la API. |
| **HU_DN_05_74** | Cabecera de columna, badge de advertencia, `WipLimitModal.tsx` | `UpdateColumnWipLimitUseCase`, `PUT /projects/{id}/kanban/columns/{col}/wip` | Configuración de entero positivo o "Sin límite" (Admin/Gerente). Advertencia soft-limit en cabecera: `'Límite WIP superado ([Actual]/[Límite])'` en color ámbar sin bloquear movimiento. Éxito: `'Límite WIP actualizado correctamente.'`. Error: `'No fue posible completar la operación. Intente nuevamente.'`. |
| **HU_DN_05_75** | `KanbanFilterBar.tsx` | Filtrado dinámico en memoria de tarjetas | Filtros combinables: texto libre, selector de responsable, selector de historia del sprint, selector de tipo de tarea. Si no hay coincidencias: `'No se encontraron tarjetas con los filtros aplicados.'` con botón para restablecer filtros. |
| **HU_DN_05_76** | Badge de bloqueo en esquina, `TaskBlockModal.tsx` | `UpdateTaskBlockUseCase`, `PATCH /projects/{id}/tasks/{id}/block`, columnas `is_blocked` y `blocked_by_task_id` | Insignia con candado rojo en esquina de la tarjeta ante impedimento o tarea predecesora incompleta. Detalle y modal al hacer hover/clic. Reporte o resolución de impedimento con mensaje `'Estado de bloqueo actualizado.'`. |

### Resumen de Quality Gates

| Repositorio | Verificación | Resultado | Estado |
|---|---|---|---|
| Backend | `pytest tests/unit tests/application tests/api` | 324 pruebas pasadas (0 fallos) | APROBADO |
| Backend | `ruff check .` | 0 errores | APROBADO |
| Backend | `ruff format --check .` | 253 archivos formateados | APROBADO |
| Backend | `lint-imports` | 3 contratos cumplidos (BR-1, BR-2, BR-4) | APROBADO |
| Frontend | `npm run typecheck` | 0 errores TypeScript | APROBADO |
| Frontend | `npm run lint` | 0 errores / 0 advertencias ESLint | APROBADO |
| Frontend | `npm run format:check` | 100% código formateado con Prettier | APROBADO |
| Frontend | `npm run test:coverage` | 310 pruebas pasadas en 40 suites (cobertura funciones: 79.61% > 78%) | APROBADO |
| Frontend | `scan-secrets.mjs` | 0 secretos en 188 archivos inspeccionados | APROBADO |



