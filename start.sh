#!/bin/bash

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Starting MQTT client worker in background..."
python manage.py run_mqtt_client &

echo "==> Starting Django web server..."
exec gunicorn \
  --worker-class gevent \
  --worker-connections 1000 \
  config.wsgi:application \
  --bind 0.0.0.0:${PORT:-8000}