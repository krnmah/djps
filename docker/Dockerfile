FROM python:3.11-slim

WORKDIR /app

# Intalling dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY app /app/app
COPY scripts/entrypoint.sh /app/entrypoint.sh

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 8000

# Start app
ENTRYPOINT [ "/app/entrypoint.sh" ]