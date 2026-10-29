#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/common.sh"
REQUIRED_MAJOR=20
_enable_pnpm(){ command_exists corepack || { log_err 'corepack no encontrado'; return 1; }; corepack enable 2>/dev/null || run_sudo corepack enable; corepack prepare pnpm@9 --activate; log_ok "pnpm $(pnpm --version) activo"; }
if command_exists node; then VER="$(node --version | sed 's/^v//')"; if [ "${VER%%.*}" -ge "$REQUIRED_MAJOR" ] 2>/dev/null; then log_ok "Node $VER ya instalado"; _enable_pnpm; exit 0; fi; fi
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT; download https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh "$TMP/install.sh"; bash "$TMP/install.sh"; fi
. "$NVM_DIR/nvm.sh"; ensure_path_line 'export NVM_DIR="$HOME/.nvm"'; ensure_path_line '[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"'; nvm install "$REQUIRED_MAJOR"; nvm alias default "$REQUIRED_MAJOR"; nvm use default
VER="$(node --version | sed 's/^v//')"; version_ge "$VER" 20.0.0 || exit 1; log_ok "Node $VER activo"; _enable_pnpm
