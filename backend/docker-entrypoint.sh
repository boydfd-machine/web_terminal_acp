#!/usr/bin/env bash
set -euo pipefail

echo "Running database migrations..."
alembic upgrade head

if [ "$#" -eq 0 ]; then
  access_log_args=()
  if [ "${UVICORN_ACCESS_LOG:-false}" != "true" ]; then
    access_log_args=(--no-access-log)
  fi

  set -- uvicorn app.main:app \
    --host "${APP_HOST:-0.0.0.0}" \
    --port "${APP_PORT:-8000}" \
    --ws-ping-interval "${WS_PING_INTERVAL:-30}" \
    --ws-ping-timeout "${WS_PING_TIMEOUT:-120}" \
    "${access_log_args[@]}"
fi

echo "Starting backend..."
exec "$@"
