#!/bin/sh
# Applies pending migrations before starting the API (idempotent), then execs the command.
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] applying database migrations"
    alembic upgrade head
fi

exec "$@"
