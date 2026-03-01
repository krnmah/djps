FROM python:3.11-slim

WORKDIR /app

# Installing dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application source
COPY app /app/app

# Copy scripts (worker entry point + entrypoint.sh)
COPY scripts /app/scripts

# Copy alembic config and migrations
COPY alembic.ini /app/alembic.ini

# Make entrypoint executable
RUN chmod +x /app/scripts/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]