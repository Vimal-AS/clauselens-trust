# Production Dockerfile for ClauseLens Trust
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (build-essential, font libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create persistent storage directories
RUN mkdir -p database uploads reports demo_contracts && \
    chmod -R 755 database uploads reports demo_contracts

ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
EXPOSE 5000

# Run with Gunicorn WSGI production server optimized for 512MB RAM cloud environments
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile - --log-level info app:app"]
