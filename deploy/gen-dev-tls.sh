#!/usr/bin/env bash
# Generate a self-signed device-port certificate for local dev/test.
# Production supplies real certificates via deploy/tls/.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)/tls"
mkdir -p "$DIR"
if [ -f "$DIR/device.crt" ] && [ "${1:-}" != "--force" ]; then
  echo "device.crt already exists (use --force to regenerate)"
  exit 0
fi
# Use a config file (not -subj) so Git-Bash does not rewrite /CN=... into a path.
CFG="$DIR/openssl.cnf"
cat > "$CFG" <<'CNF'
[req]
distinguished_name = dn
x509_extensions = v3
prompt = no
[dn]
CN = dibs-device
[v3]
subjectAltName = DNS:localhost,DNS:device,IP:127.0.0.1
CNF
openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -keyout "$DIR/device.key" -out "$DIR/device.crt" -config "$CFG"
rm -f "$CFG"
echo "wrote $DIR/device.crt and $DIR/device.key"
