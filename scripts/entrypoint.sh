#!/bin/bash
set -e

# Only run DB migrations in the api container.
# The worker skips this to avoid a race condition where both
# containers try to CREATE TABLE alembic_version at the same time.
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Running database migrations..."
    alembic upgrade head
    echo "Migrations complete."
fi

# Hand off to whatever command was passed:
#   api    -> uvicorn app.main:app ...
#   worker -> python scripts/start_worker.py
exec "$@"