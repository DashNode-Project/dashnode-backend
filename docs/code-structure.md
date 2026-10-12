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
