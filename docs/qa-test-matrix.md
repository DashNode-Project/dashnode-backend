# Matriz de pruebas QA — DashNode (estado actual)

Documento de referencia para QA manual y regresión. Prioridad: **P0** bloqueante, **P1** alto, **P2** medio.

## Entorno mínimo

| Requisito | Verificación |
|-----------|----------------|
| PostgreSQL accesible (`DATABASE_URL`) | `GET /health/ready` → 200 |
| Backend `:8000` | `GET /health` → `ok` |
| Frontend Vite `:5173` | Login carga |
| Migraciones | `alembic upgrade head` |
| Seeds dev (opcional) | Usuarios admin/manager/developer |

## 1. Autenticación y sesión (EP-01)

| ID | Caso | Pasos | Resultado esperado | P |
|----|------|-------|-------------------|---|
| AUTH-01 | Login válido | Email + password seed | Cookie de sesión, redirección al workspace | P0 |
| AUTH-02 | Credenciales inválidas | Password incorrecta | Mensaje de error, sin sesión | P0 |
| AUTH-03 | Logout | Cerrar sesión | Cookie invalidada, no accede a rutas privadas | P1 |
| AUTH-04 | Sesión expirada | Esperar TTL o borrar cookie | 401 / mensaje de sesión expirada | P1 |
| AUTH-05 | CSRF / origen | Request sin origen permitido | Rechazo según middleware | P2 |

## 2. Perfil y administración de usuarios

| ID | Caso | Resultado esperado | P |
|----|------|-------------------|---|
| PROF-01 | Ver/editar perfil propio | Datos persisten | P1 |
| PROF-02 | Avatar válido | Imagen ≤ límite, visible | P2 |
| USER-01 | Admin lista usuarios | Solo roles autorizados | P1 |
| USER-02 | Activar/desactivar usuario | RBAC respetado | P1 |

## 3. Proyectos (EP-03)

| ID | Caso | Resultado esperado | P |
|----|------|-------------------|---|
| PRJ-01 | Listar proyectos visibles | Solo proyectos con membresía/RBAC | P0 |
| PRJ-02 | Crear proyecto (manager) | Proyecto en listado | P1 |
| PRJ-03 | Editar metadatos | Cambios guardados | P1 |
| PRJ-04 | Soft delete | No visible en listado normal | P1 |
| PRJ-05 | Miembros: invitar / quitar | Roles coherentes | P1 |

## 4. Backlog, sprints, Kanban, tareas

| ID | Caso | Resultado esperado | P |
|----|------|-------------------|---|
| BL-01 | CRUD historias de usuario | Datos en proyecto correcto | P1 |
| SP-01 | CRUD sprints | Asociación a proyecto | P1 |
| KB-01 | Tablero Kanban | Columnas y tarjetas coherentes | P1 |
| TS-01 | Tareas por HU | Estados (pendiente, hecho, etc.) | P1 |

## 5. Documentación

| ID | Caso | Resultado esperado | P |
|----|------|-------------------|---|
| DOC-01 | Listar docs autorizados | Sin filtrar por aprobación indebida | P1 |
| DOC-02 | Crear / editar (rol permitido) | Persistencia y permisos | P2 |

## 6. Notificaciones y disponibilidad

| ID | Caso | Resultado esperado | P |
|----|------|-------------------|---|
| NOT-01 | Listar notificaciones | Solo del usuario | P2 |
| AVL-01 | Disponibilidad de miembros | Datos por proyecto | P2 |

## 7. Asistente IA (EP-10)

### 7.1 API

| ID | Caso | Endpoint | Resultado esperado | P |
|----|------|----------|-------------------|---|
| AI-01 | Chat historial 24h | `GET /api/v1/ai/chat/messages` | Mensajes del usuario autenticado | P1 |
| AI-02 | Texto determinista | `POST /api/v1/ai/text-generate` «qué proyectos tengo» | Lista real de proyectos | P0 |
| AI-03 | Texto con proyecto | «Cuántas HUs tiene \<nombre\>» | Conteo real RBAC | P0 |
| AI-04 | Pendientes | «Qué tengo pendiente en \<proyecto\>» | Tareas filtradas | P0 |
| AI-05 | Voz transcribe | `POST /api/v1/ai/voice-transcribe` | Texto reconocido | P1 |
| AI-06 | Voz completa | `POST /api/v1/ai/voice-process` | Transcripción + respuesta | P1 |
| AI-07 | Cuota agotada | Límite diario | Código `FREE_QUOTA_EXHAUSTED` | P2 |
| AI-08 | Sin sesión | Llamada sin cookie | 401 | P0 |

### 7.2 Matriz NLU (texto y voz)

| Entrada | Esperado |
|---------|----------|
| «proyectos» / «que proyectos» / «proyectos disponibles» | Listar proyectos |
| «Cuántas HUs tiene VozNotAI» | Resolver proyecto + conteo HUs |
| «VozNotAI» (solo nombre) | Resumen del proyecto o aclaración contextual |
| «Qué tengo pendiente en DashNode» | Tareas pendientes del proyecto resuelto |
| «Cuáles son las HUs de este proyecto» | HUs del proyecto abierto en UI |
| «Hola, hola» (voz) | Saludo, sin consulta SQL innecesaria |
| Consulta ambigua | Fallback Gemini o mensaje accionable (no error genérico si el fallo es NLU) |

### 7.3 UI (frontend)

| ID | Caso | Resultado esperado | P |
|----|------|-------------------|---|
| AI-UI-01 | Widget global | Funciona sin proyecto obligatorio | P0 |
| AI-UI-02 | Historial por usuario | No mezcla sesiones | P1 |
| AI-UI-03 | Modos voz/texto | Estados de carga distintos | P1 |
| AI-UI-04 | Timeout largo IA | No congela login (voz en thread pool) | P0 |

## 8. Seguridad transversal

| ID | Caso | Resultado esperado | P |
|----|------|-------------------|---|
| SEC-01 | RBAC en APIs | Developer no administra usuarios ajenos | P0 |
| SEC-02 | IA no inventa datos | Respuestas ancladas a SQL autorizado | P0 |
| SEC-03 | Secretos | No aparecen en logs cliente | P0 |

## 9. Regresión automatizada (CI local)

```bash
cd dashnode-backend
ruff check .
pytest -q
cd ../dashnode-frontend
npm test -- --run   # si aplica
```

Integración Gemini live (opcional): `GEMINI_INTEGRATION=1 pytest tests/integration/test_gemini_integration.py`

## 10. Criterios de salida release candidata

- Todos **P0** PASS en entorno de staging.
- **P1** PASS ≥ 95 % o con incidencias documentadas.
- Sin errores `ruff check` en backend.
- Login + listado proyectos + 3 consultas IA deterministas verificadas en la misma sesión.
