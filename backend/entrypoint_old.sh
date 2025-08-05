#!/bin/bash

set -e

echo "Waiting for MySQL to be ready..."

# Wait for MySQL to be ready
until mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1" > /dev/null 2>&1; do
  echo "MySQL is unavailable - sleeping"
  sleep 2
done

echo "MySQL is up - continuing..."

# Wait for Meilisearch to be ready
echo "Waiting for Meilisearch to be ready..."
MEILI_HOST=${MEILISEARCH_HOST:-localhost}
MEILI_PORT=${MEILISEARCH_PORT:-7700}

until curl -s "http://$MEILI_HOST:$MEILI_PORT/health" > /dev/null 2>&1; do
  echo "Meilisearch is unavailable - sleeping"
  sleep 3
done

echo "Meilisearch is up - continuing..."

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Making migrations..."
python manage.py makemigrations

echo "Running migrations..."
python manage.py migrate

echo "Creating superuser if it doesn't exist..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@gamil.com', 'admin')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
"

# Setup Meilisearch indices and index OCR data
echo "Setting up Meilisearch..."
python manage.py setup_meilisearch

# Choose server type based on environment variable
SERVER_TYPE=${SERVER_TYPE:-"uvicorn"}

if [ "$SERVER_TYPE" = "uvicorn" ]; then
    echo "Starting Django with Uvicorn (ASGI) server..."
    exec uvicorn core.asgi:application --host 0.0.0.0 --port 8000 --reload
else
    echo "Starting Django development server (WSGI)..."
    exec python manage.py runserver 0.0.0.0:8000
fi
