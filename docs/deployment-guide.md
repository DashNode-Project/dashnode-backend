# Guía de despliegue — Backend DashNode

## Requisitos

- Python 3.12+
- PostgreSQL accesible (local Docker o Supabase)
- Variables en `.env` (copiar desde `.env.example`)

## Supabase (PostgreSQL gestionado)

1. En el panel de Supabase, copie la cadena **URI** de conexión (modo `session` o `direct`).
2. Arme `DATABASE_URL` en `.env` con el usuario, host, puerto, base y `sslmode=require`.
   Use la contraseña del panel **solo** en `.env` (git-ignored), nunca en documentación versionada.
   En `.env.example` hay un marcador `CHANGE_ME_DB_PASSWORD` y host `YOUR_PROJECT`.

3. Ejemplo de forma (sustituya valores reales únicamente en su `.env` local):

   `postgresql+psycopg://postgres:CHANGE_ME_DB_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres?sslmode=require`

## Migraciones y datos semilla

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
alembic upgrade head
python -m app.cli.seed
```

El seed crea usuarios demo (`SEED_*` en `.env`). Está deshabilitado si `APP_ENV=production`; use `APP_ENV=development` solo para la carga inicial y luego pase a `production`.

## Ejecutar la API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Verificación

```bash
pytest -m "not integration"
curl http://127.0.0.1:8000/health
```

## Avatares

Los archivos subidos se guardan en `data/avatars/` (configurable con `AVATAR_STORAGE_DIR`). En despliegues con varias réplicas, use almacenamiento compartido o S3 en una iteración futura.
