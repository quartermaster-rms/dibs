#!/usr/bin/env bash
# Lint every tracked shell script with shellcheck. Uses the shellcheck binary if
# present, otherwise the official Docker image, so no local install is required
# (the project already depends on Docker for the deploy checks).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mapfile -t files < <(git ls-files '*.sh')
[ ${#files[@]} -eq 0 ] && exit 0

if command -v shellcheck >/dev/null 2>&1; then
  shellcheck "${files[@]}"
else
  # No local binary: use the official image. On Windows Git Bash the mount source
  # must be a Windows-style path and MSYS must not rewrite the container paths.
  win_root="$(pwd -W 2>/dev/null || pwd)"
  MSYS_NO_PATHCONV=1 docker run --rm -v "${win_root}:/src" -w /src \
    koalaman/shellcheck:stable "${files[@]}"
fi
