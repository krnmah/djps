#!/bin/bash

# invoking migration
alembic upgrade head

# invoking uvicorn
exec uvicorn app.main:app --host 0.0.0.0 --port 8000