#!/usr/bin/env bash
# Deploy the stack. If the new image set fails its health check, make one
# bounded, same-invocation attempt to reactivate the immediately previous image
# set (pinned to the exact image), then exit non-zero. Migrations are never
# rolled back; there is no operator rollback command or cached-image selector
# (IMPLEMENTATION-GUIDE §8).
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
[ -f host.env ] || { echo "deploy/host.env is required" >&2; exit 1; }

compose() { docker compose --env-file host.env -f docker-compose.yml "$@"; }

# Pin the currently-deployed image as the rollback target.
if docker image inspect dibs:latest >/dev/null 2>&1; then
  docker tag dibs:latest dibs:previous
fi

compose build
compose up -d

api_healthy() {
  local cid
  cid="$(compose ps -q api)"
  [ -n "$cid" ] || return 1
  [ "$(docker inspect --format '{{.State.Health.Status}}' "$cid" 2>/dev/null)" = healthy ]
}

for _ in $(seq 1 60); do
  if api_healthy; then
    echo "deploy healthy"
    exit 0
  fi
  sleep 3
done

echo "new image set failed its health check; reactivating the previous image set" >&2
if docker image inspect dibs:previous >/dev/null 2>&1; then
  docker tag dibs:previous dibs:latest
  compose up -d
fi
exit 1
