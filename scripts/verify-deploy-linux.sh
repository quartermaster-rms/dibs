#!/usr/bin/env bash
# Faithfully reproduce the CI `test-deploy` job on a non-Linux host.
#
# Windows Docker Desktop does not enforce Linux file permissions on bind mounts
# from the Windows filesystem, so `make test-deploy` there cannot catch bugs
# like a device TLS key the non-root container user (uid 10001) cannot read.
# This runs the real scripts/test-deploy.sh inside a Linux docker-in-docker
# container, with the repo on the container's own ext4 filesystem, so bind-mount
# semantics match the GitHub runner exactly. It uses only the host Docker daemon
# and changes nothing outside this repo.
#
# On a native Linux host just run `make test-deploy` directly; this wrapper is
# only needed where the host filesystem is not Linux.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIND_IMAGE="${DIND_IMAGE:-docker:27-dind}"
DHOST="-e DOCKER_HOST=unix:///var/run/docker.sock"

command -v docker >/dev/null || { echo "docker is required on the host"; exit 1; }

echo ">> starting docker-in-docker ($DIND_IMAGE)"
CID="$(docker run -d --privileged -e DOCKER_TLS_CERTDIR= "$DIND_IMAGE")"
cleanup() { docker rm -f "$CID" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo ">> waiting for the inner docker daemon"
docker exec $DHOST "$CID" sh -c \
  'for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && exit 0; sleep 1; done; exit 1' \
  || { echo "inner docker daemon did not start"; exit 1; }

echo ">> installing gate dependencies"
docker exec "$CID" sh -c 'apk add --no-cache bash openssl curl grep coreutils >/dev/null'

echo ">> copying the working tree onto the container ext4 filesystem"
tar -c -C "$ROOT" \
  --exclude=.git --exclude=.agent --exclude=.venv \
  --exclude=node_modules --exclude=frontend/node_modules \
  --exclude=frontend/dist --exclude=deploy/tls \
  --exclude='__pycache__' --exclude='*.pyc' \
  . | docker exec -i "$CID" sh -c 'mkdir -p /work && tar -x -C /work'

echo ">> running the real test-deploy gate on Linux (this builds the image)"
docker exec $DHOST "$CID" bash -c 'cd /work && bash scripts/test-deploy.sh'
