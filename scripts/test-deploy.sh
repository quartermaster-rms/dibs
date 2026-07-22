#!/usr/bin/env bash
# Build and verify the production Docker artifact end to end: the stack boots,
# runs non-root, applies migrations, serves the api + SPA + device port, and
# keeps Postgres/Redis internal.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY="$ROOT/deploy"
cd "$DEPLOY"

PROJECT="dibs-testdeploy"
API_PORT="${DIBS_TESTDEPLOY_API_PORT:-18080}"
DEVICE_PORT="${DIBS_TESTDEPLOY_DEVICE_PORT:-18443}"
ENVFILE="$DEPLOY/host.env"
BACKUP=""

compose() { docker compose -p "$PROJECT" -f "$DEPLOY/docker-compose.yml" "$@"; }

cleanup() {
  compose down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f "$ENVFILE"
  [ -n "$BACKUP" ] && mv "$BACKUP" "$ENVFILE"
  rm -f /tmp/dibs-testdeploy-cookies.txt
}
trap cleanup EXIT

[ -f "$ENVFILE" ] && { BACKUP="$ENVFILE.bak.$$"; mv "$ENVFILE" "$BACKUP"; }
cat > "$ENVFILE" <<EOF
POSTGRES_USER=dibs
POSTGRES_PASSWORD=dibs
POSTGRES_DB=dibs
DATABASE_URL=postgresql+psycopg://dibs:dibs@postgres:5432/dibs
REDIS_URL=redis://redis:6379/0
PLATFORM_TZ=America/Los_Angeles
AUTH_MODE=stub
SESSION_SECRET=testdeploy-secret
COOKIE_SECURE=false
API_PORT=$API_PORT
DEVICE_PORT=$DEVICE_PORT
DEVICE_TLS_CERT=/tls/device.crt
DEVICE_TLS_KEY=/tls/device.key
EOF

bash "$DEPLOY/gen-dev-tls.sh" >/dev/null

echo ">> build"; compose build
echo ">> up";    compose up -d

echo ">> wait for health"
for svc in api device; do
  status=starting
  for _ in $(seq 1 90); do
    cid="$(compose ps -q "$svc")"
    status="$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo starting)"
    [ "$status" = healthy ] && break
    [ "$status" = unhealthy ] && break
    sleep 2
  done
  if [ "$status" != healthy ]; then
    echo "FAIL: $svc is $status"; compose logs "$svc" | tail -40; exit 1
  fi
done

API="http://127.0.0.1:$API_PORT"
DEV="https://127.0.0.1:$DEVICE_PORT"
fail() { echo "FAIL: $1"; exit 1; }

echo ">> runs non-root"
uid="$(compose exec -T api id -u | tr -d '\r')"
[ "$uid" = 10001 ] || fail "api not non-root (uid=$uid)"

echo ">> migrations applied"
compose exec -T api alembic current 2>&1 | grep -q 0001 || fail "migrations not at head"

echo ">> api plane"
curl -fsS "$API/healthz" | grep -q '"status": *"ok"' || fail "healthz"
curl -fsS -c /tmp/dibs-testdeploy-cookies.txt -X POST "$API/api/auth/stub-login" \
  -H 'content-type: application/json' \
  -d '{"subject":"smoke","display_name":"Smoke","email":"s@x","groups":["admin-dibs"]}' \
  | grep -q '"subject": *"smoke"' || fail "stub-login"
curl -fsS -b /tmp/dibs-testdeploy-cookies.txt "$API/api/me" | grep -q '"is_admin": *true' || fail "me"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$API/api/does-not-exist")" = 404 ] || fail "unknown api not 404"
curl -fsS "$API/" | grep -qi 'dibs' || fail "SPA index not served"

echo ">> device plane"
[ "$(curl -sk -o /dev/null -w '%{http_code}' "$DEV/device/nodes/00000000-0000-0000-0000-000000000000/desired-state")" = 401 ] \
  || fail "device port not requiring a node key"
curl -fsSk "$DEV/healthz" | grep -q ok || fail "device healthz"

echo ">> postgres/redis stay internal"
for svc in postgres redis; do
  compose port "$svc" 5432 >/dev/null 2>&1 && fail "$svc is published" || true
done

echo ">> OK: production image verified"
