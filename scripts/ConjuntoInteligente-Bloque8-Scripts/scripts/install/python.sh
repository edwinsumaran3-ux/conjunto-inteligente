#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/common.sh"
REQUIRED=3.12; OS="$(detect_os)"; DISTRO="$(detect_distro)"
install_poetry(){ if command_exists poetry; then log_ok "Poetry ya instalado"; return; fi; if command_exists pipx; then pipx install poetry; else "python${REQUIRED}" -m pip install --user --quiet poetry || python3 -m pip install --user --quiet poetry; ensure_path_line 'export PATH="$HOME/.local/bin:$PATH"'; export PATH="$HOME/.local/bin:$PATH"; fi; command_exists poetry || log_warn "Poetry instalado pero requiere recargar PATH"; }
if command_exists "python${REQUIRED}"; then VER="$(python${REQUIRED} --version | awk '{print $2}')"; version_ge "$VER" 3.12.0 || true; install_poetry; exit 0; fi
case "$OS-$DISTRO" in
 linux-ubuntu|linux-debian|linux-linuxmint|linux-pop) run_sudo apt-get update -qq; run_sudo apt-get install -y -qq software-properties-common; run_sudo add-apt-repository -y ppa:deadsnakes/ppa; run_sudo apt-get update -qq; run_sudo apt-get install -y -qq python3.12 python3.12-venv python3.12-dev python3-pip python3-venv;;
 linux-fedora|linux-rhel|linux-centos|linux-rocky) run_sudo dnf install -y python3.12 python3.12-devel python3-pip;;
 linux-arch|linux-manjaro) run_sudo pacman -Sy --noconfirm python python-pip;;
 macos-*) command_exists brew || { log_err "Homebrew requerido: https://brew.sh"; exit 1; }; brew install python@3.12;;
 *) log_err "Distribución no soportada: $OS-$DISTRO"; exit 1;; esac
command_exists python3.12 || { log_err "python3.12 no disponible tras instalación"; exit 1; }; VER="$(python3.12 --version | awk '{print $2}')"; log_ok "Python $VER instalado"; install_poetry
