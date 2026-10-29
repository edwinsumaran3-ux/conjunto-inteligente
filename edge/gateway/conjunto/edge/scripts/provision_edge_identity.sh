#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:?Uso: provision_edge_identity.sh <directorio_salida> [device-id]}"
DEVICE_ID="${2:?Uso: provision_edge_identity.sh <directorio_salida> <device-id>}"
mkdir -p "$OUT_DIR"
umask 077
openssl genpkey -algorithm ED25519 -out "$OUT_DIR/device-private.pem"
openssl pkey -in "$OUT_DIR/device-private.pem" -pubout -out "$OUT_DIR/device-public.pem"
openssl pkey -pubin -in "$OUT_DIR/device-public.pem" -outform DER | sha256sum | awk '{print $1}' > "$OUT_DIR/device-public.sha256"
printf 'device_id=%s\npublic_key_sha256=%s\n' "$DEVICE_ID" "$(cat "$OUT_DIR/device-public.sha256")" > "$OUT_DIR/device-registration.txt"
printf 'Private key: %s\nPublic key: %s\n' "$OUT_DIR/device-private.pem" "$OUT_DIR/device-public.pem"
printf 'Register the PUBLIC key only; keep device-private.pem outside source control and provision it through the secret manager.\n'
