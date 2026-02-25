FROM python:3.11-slim

WORKDIR /app

# Intalling dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY app /app/app

# Expose port
EXPOSE 8000

# Start app
CMD [ "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000" ]