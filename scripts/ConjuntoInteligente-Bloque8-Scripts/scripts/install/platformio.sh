#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/common.sh"
install_esp(){ export PATH="$HOME/.local/bin:$PATH"; pio pkg install --global --platform espressif32 2>/dev/null || log_warn 'No se pudo preinstalar espressif32; se descargará al primer build.'; }
if command_exists pio; then log_ok "PlatformIO $(pio --version) ya instalado"; install_esp; exit 0; fi
if command_exists pipx; then pipx install platformio; elif command_exists python3.12; then python3.12 -m pip install --user --quiet --upgrade platformio; else log_err 'Se requiere Python 3.12. Ejecuta --python primero.'; exit 1; fi
export PATH="$HOME/.local/bin:$PATH"; ensure_path_line 'export PATH="$HOME/.local/bin:$PATH"'; command_exists pio || { log_err 'pio no disponible tras instalación'; exit 1; }; log_ok "PlatformIO $(pio --version) instalado"; install_esp
