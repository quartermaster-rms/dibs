#!/usr/bin/env bash
# Dispatch container role. The one-shot `init` role creates the schema and exits;
# every long-running role waits for it (compose service_completed_successfully),
# so no process queries a table before it exists. No role re-evaluates a session.
set -euo pipefail

role="${1:-api}"
case "$role" in
  init)
    exec python -m dibs.schema
    ;;
  api)
    # Plain HTTP for a TLS-terminating reverse proxy to sit in front of. Trust
    # that proxy's X-Forwarded-* so the app sees the real scheme/host (https,
    # OIDC redirect URLs, Secure cookies). The api is internal/loopback-only.
    exec gunicorn dibs.app:app \
      -k uvicorn.workers.UvicornWorker \
      -b 0.0.0.0:8000 \
      -w "${WEB_CONCURRENCY:-2}" \
      --forwarded-allow-ips '*' \
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
