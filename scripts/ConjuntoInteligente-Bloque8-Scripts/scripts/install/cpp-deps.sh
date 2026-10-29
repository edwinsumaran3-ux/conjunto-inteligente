#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/common.sh"
OS="$(detect_os)"; DISTRO="$(detect_distro)"
install_paho_source(){ local tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' RETURN; git clone --depth 1 --branch v1.3.13 https://github.com/eclipse/paho.mqtt.c.git "$tmp/paho"; cmake -S "$tmp/paho" -B "$tmp/paho/build" -DPAHO_BUILD_SHARED=TRUE -DPAHO_BUILD_STATIC=TRUE -DPAHO_WITH_SSL=TRUE -DPAHO_ENABLE_TESTING=FALSE; cmake --build "$tmp/paho/build" -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)"; run_sudo cmake --install "$tmp/paho/build"; run_sudo ldconfig 2>/dev/null || true; }
check_base(){ command_exists cmake && command_exists ninja && command_exists gcc && command_exists g++ && command_exists pkg-config && pkg-config --exists sqlite3 2>/dev/null; }
if check_base; then log_ok 'Dependencias C++ base presentes'; else
 case "$OS-$DISTRO" in
 linux-ubuntu|linux-debian|linux-linuxmint|linux-pop) run_sudo apt-get update -qq; run_sudo apt-get install -y -qq build-essential cmake ninja-build pkg-config git curl libssl-dev libsqlite3-dev zlib1g-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libopencv-dev; run_sudo apt-get install -y -qq libpaho-mqtt-dev || install_paho_source;;
 linux-fedora|linux-rhel|linux-centos|linux-rocky) run_sudo dnf install -y @development-tools cmake ninja-build pkg-config git curl openssl-devel sqlite-devel zlib-devel; run_sudo dnf install -y paho-c-devel || install_paho_source;;
 linux-arch|linux-manjaro) run_sudo pacman -Sy --noconfirm base-devel cmake ninja pkgconf git curl openssl sqlite paho-mqtt-c;;
 macos-*) command_exists brew || { log_err 'Homebrew requerido'; exit 1; }; brew install cmake ninja pkg-config openssl sqlite eclipse-paho-mqtt-c;;
 *) log_err "OS no soportado: $OS-$DISTRO"; exit 1;; esac
fi
for c in cmake ninja gcc g++ pkg-config; do command_exists "$c" || { log_err "$c no encontrado"; exit 1; }; done; log_ok 'Dependencias C++ verificadas'; has_header MQTTClient.h && log_ok 'Paho MQTT header presente' || log_warn 'MQTTClient.h no encontrado'
pkg-config --exists sqlite3 2>/dev/null && log_ok "SQLite $(pkg-config --modversion sqlite3)" || { log_err 'sqlite3 dev no encontrado'; exit 1; }
