#!/usr/bin/env bash
# Dispatch container role. The api role applies forward-only migrations before
# serving (expand phase); no role ever re-evaluates a session.
set -euo pipefail

role="${1:-api}"
case "$role" in
  api)
    alembic upgrade head
    exec gunicorn dibs.app:app \
      -k uvicorn.workers.UvicornWorker \
      -b 0.0.0.0:8000 \
      -w "${WEB_CONCURRENCY:-2}" \
      --access-logfile - --error-logfile -
    ;;
  worker)
    exec python -m dibs.workers.worker
    ;;
  scheduler)
    exec python -m dibs.workers.scheduler
    ;;
  device)
    # Always listen on the fixed internal port 8443; compose publishes
    # ${DEVICE_PORT} -> 8443 on the host.
    exec uvicorn dibs.device.app:app \
      --host 0.0.0.0 --port 8443 \
      --ssl-certfile "${DEVICE_TLS_CERT}" --ssl-keyfile "${DEVICE_TLS_KEY}"
    ;;
  *)
    echo "unknown role: $role" >&2
    exit 1
    ;;
esac
