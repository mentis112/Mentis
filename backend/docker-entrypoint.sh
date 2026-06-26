#!/usr/bin/env sh
set -eu

python -m app.cli.wait_for_db
alembic upgrade head

if [ "${SEED_DEMO_USER:-true}" = "true" ]; then
  python -m app.cli.seed_demo
fi

exec "$@"
