#!/bin/bash
# Backend entrypoint script for Docker

set -e

echo "Starting AI MetroFlow Backend..."

# Wait for database to be ready
echo "Waiting for PostgreSQL..."
while ! pg_isready -h "${POSTGRES_SERVER:-localhost}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-metroflow}" > /dev/null 2>&1; do
    sleep 1
done
echo "PostgreSQL is ready!"

# Wait for MongoDB to be ready
echo "Waiting for MongoDB..."
while ! mongosh --eval "db.adminCommand('ping')" --host "${MONGODB_URI:-mongodb://localhost:27017}" > /dev/null 2>&1; do
    sleep 1
done
echo "MongoDB is ready!"

# Wait for Redis to be ready
echo "Waiting for Redis..."
while ! redis-cli -h "${REDIS_HOST:-localhost}" -p "${REDIS_PORT:-6379}" ping > /dev/null 2>&1; do
    sleep 1
done
echo "Redis is ready!"

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Initialize default data
echo "Initializing default data..."
python -c "
import asyncio
from app.core.database import init_db
from app.main import init_default_data
asyncio.run(init_db())
asyncio.run(init_default_data())
print('Default data initialized!')
"

# Start the application
echo "Starting FastAPI application..."
exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --reload