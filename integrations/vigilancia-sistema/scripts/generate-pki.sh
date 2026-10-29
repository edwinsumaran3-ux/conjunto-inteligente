#!/usr/bin/env bash
set -euo pipefail
OUT=${1:-./infrastructure/pki}
mkdir -p "$OUT"
umask 077
openssl genrsa -out "$OUT/ca.key" 4096
openssl req -x509 -new -nodes -key "$OUT/ca.key" -sha256 -days 3650 -out "$OUT/ca.crt" -subj "/CN=Vigilancia-CA"
openssl genrsa -out "$OUT/server.key" 4096
openssl req -new -key "$OUT/server.key" -out "$OUT/server.csr" -subj "/CN=mosquitto"
openssl x509 -req -in "$OUT/server.csr" -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" -CAcreateserial -out "$OUT/server.crt" -days 825 -sha256
rm -f "$OUT/server.csr" "$OUT/ca.srl"
echo "PKI created in $OUT. Do not commit private keys."
