#!/bin/bash
set -e

echo "Waiting for database to be ready..."
sleep 5

echo "Running database migrations..."
alembic upgrade head || echo "Migrations failed or already applied"

# Seed data only if SEED_DATA environment variable is set
if [ "$SEED_DATA" = "true" ]; then
    echo "Running seed data..."
    python seed.py || echo "Seed data failed or already exists"
fi

echo "Starting application..."
exec "$@"
