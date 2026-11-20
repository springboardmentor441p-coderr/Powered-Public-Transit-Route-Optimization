FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Build frontend
WORKDIR /app/frontend
RUN npm ci && npm run build

WORKDIR /app

# Expose backend port
EXPOSE 8000

# Run pipeline, train models, and serve API
CMD ["sh", "-c", "python analytics/run_pipeline.py && python train_models.py && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
