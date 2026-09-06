FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set PYTHONPATH so refyne module is discovered
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn refyne.main:app --host 0.0.0.0 --port 8000"]
