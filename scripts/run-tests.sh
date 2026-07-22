#!/usr/bin/env bash
# Run the dibs test suite hermetically. Uses env-provided DATABASE_URL/REDIS_URL
# when set (CI service containers); otherwise starts ephemeral, isolated
# Postgres/Redis containers on non-default ports so it never collides with or
# reuses any other instance on the Docker host.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python}"
PG_CONTAINER="dibs-test-pg"
REDIS_CONTAINER="dibs-test-redis"
PG_PORT="${DIBS_TEST_PG_PORT:-55432}"
REDIS_PORT="${DIBS_TEST_REDIS_PORT:-56379}"

STARTED=0
cleanup() {
  if [ "$STARTED" = "1" ]; then
    docker rm -f "$PG_CONTAINER" "$REDIS_CONTAINER" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [ -z "${DATABASE_URL:-}" ]; then
  echo ">> starting ephemeral test services (pg:$PG_PORT redis:$REDIS_PORT)"
  docker rm -f "$PG_CONTAINER" "$REDIS_CONTAINER" >/dev/null 2>&1 || true
  docker run -d --name "$PG_CONTAINER" \
    -e POSTGRES_PASSWORD=dibs -e POSTGRES_USER=dibs -e POSTGRES_DB=dibs_test \
    -p "127.0.0.1:${PG_PORT}:5432" postgres:16-alpine >/dev/null
  docker run -d --name "$REDIS_CONTAINER" \
    -p "127.0.0.1:${REDIS_PORT}:6379" redis:7-alpine >/dev/null
  STARTED=1
  export DATABASE_URL="postgresql+psycopg://dibs:dibs@127.0.0.1:${PG_PORT}/dibs_test"
  export REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/0"
  echo ">> waiting for postgres"
  for _ in $(seq 1 60); do
    if docker exec "$PG_CONTAINER" pg_isready -U dibs -d dibs_test >/dev/null 2>&1; then break; fi
    sleep 0.5
  done
fi

# Tests run under the hermetic stub-login profile.
export AUTH_MODE="${AUTH_MODE:-stub}"
export PLATFORM_TZ="${PLATFORM_TZ:-America/Los_Angeles}"

echo ">> migrating"
$PYTHON -m alembic upgrade head

echo ">> pytest"
$PYTHON -m pytest --cov=dibs --cov-branch --cov-report=term-missing \
  --cov-report=xml --cov-report=json:coverage.json "$@"

echo ">> security-path coverage gate"
$PYTHON scripts/check_security_coverage.py

if [ "${DIBS_SKIP_FRONTEND:-0}" != "1" ]; then
  if command -v npm >/dev/null 2>&1; then
    echo ">> frontend tests"
    (cd frontend && npm ci --no-audit --no-fund --silent && npm run test -- --run)
  else
    echo ">> npm not found; skipping frontend tests"
  fi
fi

echo ">> OK"
