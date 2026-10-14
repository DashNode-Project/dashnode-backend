# Guía de despliegue — Backend DashNode (Render + Supabase)

Esta guía describe cómo publicar la **API** en [Render](https://render.com) usando **PostgreSQL en Supabase** (o cualquier Postgres gestionado). El frontend se despliega en Vercel según `dashnode-frontend/docs/deployment-guide.md`.

**Nunca** pegue contraseñas, tokens ni `DATABASE_URL` completas en el repositorio, en el PR ni en esta documentación. Configure todo en el panel de Render / Supabase.

---

## 1. Arquitectura recomendada

| Componente | Servicio | Notas |
|------------|----------|--------|
| SPA (React) | **Vercel** | Proxy `/api` hacia Render (misma origin para la cookie de sesión) |
| API (FastAPI) | **Render Web Service** | Python 3.12, migraciones al arrancar |
| Base de datos | **Supabase** (Postgres) | `sslmode=require` en la URL |

La sesión usa cookie `HttpOnly` con `SameSite=Lax`. Por eso el navegador debe llamar a la API **como mismo sitio** (proxy en Vercel) o desde orígenes explícitos en `CORS_ORIGINS` con el flujo documentado en el frontend.

---

## 2. Supabase (PostgreSQL)

1. Cree un proyecto en Supabase.
2. En **Project Settings → Database**, copie el host, puerto, usuario y nombre de base (`postgres` por defecto).
3. Genere o rote la contraseña de la base y guárdela **solo** en Render (variable `DATABASE_URL`), no en git.

4. Arme `DATABASE_URL` con el driver SQLAlchemy (sustituya marcadores en su panel, no aquí):

   - Forma (sustituya host y use `CHANGE_ME_DB_PASSWORD` como en `.env.example`):  
     `postgresql+psycopg://postgres:CHANGE_ME_DB_PASSWORD@HOST.supabase.co:5432/postgres?sslmode=require`
   - Si la contraseña tiene caracteres especiales, URL-encódelos.

5. Desde su máquina (con `.env` local git-ignored), puede validar:

   ```bash
   pip install -e ".[dev]"
   alembic upgrade head
   python -m app.cli.seed
   ```

   El seed exige `SEED_*` definidos y **no** corre con `APP_ENV=production`. Para la primera carga en Supabase use `APP_ENV=development` solo en local o en un **Render Shell** puntual, luego deje `APP_ENV=production`.

---

## 3. Render — Web Service (API)

### 3.1 Crear el servicio

1. [Render Dashboard](https://dashboard.render.com) → **New → Web Service**.
2. Conecte el repositorio `dashnode-backend` y la rama a desplegar (`develop` o `feature/...`).
3. **Root Directory:** deje vacío si el repo es solo backend; si el monorepo incluye backend, indique `dashnode-backend`.

### 3.2 Entorno

| Campo | Valor recomendado |
|--------|-------------------|
| Runtime | **Python 3** |
| Region | La más cercana a Supabase / usuarios |
| Branch | Su rama estable |

### 3.3 Build & Start

**Opción A — Python nativo (sin Docker)**

| Campo | Comando |
|--------|---------|
| Build Command | `pip install --upgrade pip && pip install .` |
| Start Command | `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

Render inyecta `$PORT`; no hardcodee `8000` en producción.

**Opción B — Docker**

Use el `Dockerfile` del repo. El entrypoint ya ejecuta `alembic upgrade head` cuando `RUN_MIGRATIONS=true` (por defecto).

### 3.4 Variables de entorno (Render → Environment)

Configure en el panel. Valores sensibles **solo** allí.

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `APP_ENV` | Sí | `production` |
| `DATABASE_URL` | Sí | URL Postgres (Supabase) con `postgresql+psycopg://` y `sslmode=require` |
| `SESSION_COOKIE_SECURE` | Sí | `true` (HTTPS) |
| `SESSION_COOKIE_SAMESITE` | Sí | `lax` (con proxy Vercel en `/api`) |
| `CORS_ORIGINS` | Sí | Orígenes del frontend separados por coma, **sin** `*`. Ej.: `https://su-app.vercel.app` |
| `FRONTEND_BASE_URL` | Sí | URL pública del frontend en Vercel (correos futuros) |
| `ARGON2_TIME_COST` | Sí | `3` (o ≥ `2` en producción) |
| `ARGON2_MEMORY_COST_KIB` | Sí | `65536` (≥ `19456` en producción) |
| `ARGON2_PARALLELISM` | Sí | `4` |
| `LOGIN_MAX_FAILED_ATTEMPTS` | Recomendado | `5` |
| `LOGIN_ATTEMPT_WINDOW_MINUTES` | Recomendado | `15` |
| `SESSION_TTL_HOURS` | Recomendado | `8` |
| `SESSION_COOKIE_RETENTION_HOURS` | Recomendado | `24` |
| `SEED_*` | Solo seed | Ver `.env.example`; no necesarias en runtime si ya sembró la BD |

No suba `TEST_POSTGRES_URL` a Render salvo que ejecute tests allí (no es el caso habitual).

### 3.5 Health check

En Render, **Health Check Path:** `/health`  
Debe responder `{"status":"ok"}`.

### 3.6 URL pública

Tras el despliegue anote la URL HTTPS del servicio, por ejemplo:

`https://dashnode-api-XXXX.onrender.com`

La usará en Vercel (proxy o `VITE_API_BASE_URL`). No incluya credenciales en la URL.

---

## 4. Datos iniciales (seed) en producción

1. Render → su servicio → **Shell** (o ejecute en local contra Supabase).
2. Exporte temporalmente `APP_ENV=development` y las variables `SEED_*` (ver `.env.example`, contraseñas fuertes generadas por usted).
3. Ejecute: `python -m app.cli.seed`
4. Vuelva a `APP_ENV=production` y elimine `SEED_*` del entorno de runtime si lo desea.

---

## 5. Avatares y disco en Render

Los avatares se guardan en `data/avatars/` (variable `AVATAR_STORAGE_DIR`). En Render el disco del contenedor es **efímero**: reinicios pueden borrar archivos. Para producción seria planifique almacenamiento compartido (S3, volumen, etc.).

---

## 6. Desarrollo local (resumen)

```bash
python scripts/generate_env.py   # crea .env local (git-ignored)
pip install -e ".[dev]"
alembic upgrade head
python -m app.cli.seed
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Docker: `docker compose up --build` (ver `README.md`).

---

## 7. Verificación post-despliegue

1. `GET https://SU-SERVICIO.onrender.com/health` → OK.
2. Desde el frontend en Vercel, inicio de sesión con un usuario semilla.
3. Compruebe **Usuarios**, **Mi perfil** y cierre de sesión.

Si recibe `403` en POST/PATCH, revise que la URL del frontend esté en `CORS_ORIGINS` y que Vercel envíe el proxy `/api` correctamente.
