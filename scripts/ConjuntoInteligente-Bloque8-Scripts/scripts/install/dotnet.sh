#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/common.sh"
REQUIRED_MAJOR=8; INSTALL_DIR="${DOTNET_INSTALL_DIR:-$HOME/.dotnet}"
if command_exists dotnet; then VER="$(dotnet --version 2>/dev/null || echo 0.0.0)"; if [ "${VER%%.*}" -ge "$REQUIRED_MAJOR" ] 2>/dev/null; then log_ok ".NET $VER ya instalado"; exit 0; fi; fi
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT; download https://dot.net/v1/dotnet-install.sh "$TMP/dotnet-install.sh"; chmod +x "$TMP/dotnet-install.sh"; "$TMP/dotnet-install.sh" --channel "$REQUIRED_MAJOR.0" --install-dir "$INSTALL_DIR" --no-path
export PATH="$INSTALL_DIR:$HOME/.dotnet/tools:$PATH"; ensure_path_line "export PATH=\"$INSTALL_DIR:\$PATH\""; ensure_path_line 'export PATH="$HOME/.dotnet/tools:$PATH"'
for tool in dotnet-ef dotnet-format; do if ! dotnet tool list --global 2>/dev/null | grep -q " $tool "; then dotnet tool install --global "$tool"; fi; done
VER="$(dotnet --version)"; version_ge "$VER" 8.0.100 || { log_err ".NET $VER no cumple >= 8.0.100"; exit 1; }; log_ok ".NET SDK $VER instalado"; dotnet ef --version >/dev/null 2>&1 || true
