# Guía de despliegue — Backend DashNode

## Requisitos

- Python 3.12+
- PostgreSQL accesible (local Docker o Supabase)
- Variables en `.env` (copiar desde `.env.example`)

## Supabase (PostgreSQL gestionado)

1. En el panel de Supabase, copie la cadena **URI** de conexión (modo `session` o `direct`).
2. Conviértala al formato SQLAlchemy:

   `postgresql+psycopg://postgres:SU_CONTRASEÑA@db.PROJECT_REF.supabase.co:5432/postgres?sslmode=require`

3. Guarde la cadena en `.env` como `DATABASE_URL`. **No suba contraseñas al repositorio.**

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
