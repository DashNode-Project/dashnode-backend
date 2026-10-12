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
