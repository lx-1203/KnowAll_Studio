FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (minimal for slim image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create persistent data directories
RUN mkdir -p /app/data/documents /app/data/exports /app/data/vector_db

# Non-root user for security
RUN useradd -m -u 1000 knowall && chown -R knowall:knowall /app
USER knowall

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
