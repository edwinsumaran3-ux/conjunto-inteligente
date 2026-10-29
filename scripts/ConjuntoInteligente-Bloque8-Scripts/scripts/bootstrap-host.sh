#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

DO_DOTNET=0; DO_PYTHON=0; DO_NODE=0; DO_CPP=0; DO_PIO=0; DO_TERRAFORM=0; DO_BUF=0; CHECK_ONLY=0; NO_SUDO=0; ANY_EXPLICIT=0
print_help(){ cat <<'HELP'
Bootstrap de Conjunto Inteligente
Uso: ./scripts/bootstrap-host.sh [--all|flags]

--all       Instala todo: .NET 8, Python 3.12, Node 20+pnpm, C++, PlatformIO, Terraform y buf.
--dotnet    Solo .NET 8 SDK.
--python    Solo Python 3.12 + Poetry.
--node      Solo Node 20 + pnpm 9.
--cpp       Solo dependencias C++.
--pio       Solo PlatformIO + espressif32.
--terraform Solo Terraform >= 1.7.
--buf       Solo buf CLI.
--check     Solo verifica; no instala.
--no-sudo   Deshabilita sudo.
--help      Ayuda.
Variables: CI=1 modo no interactivo; NO_COLOR=1 sin colores.
HELP
}
while [ $# -gt 0 ]; do case "$1" in
  --all) DO_DOTNET=1; DO_PYTHON=1; DO_NODE=1; DO_CPP=1; DO_PIO=1; DO_TERRAFORM=1; DO_BUF=1; ANY_EXPLICIT=1;;
  --dotnet) DO_DOTNET=1; ANY_EXPLICIT=1;; --python) DO_PYTHON=1; ANY_EXPLICIT=1;; --node) DO_NODE=1; ANY_EXPLICIT=1;; --cpp) DO_CPP=1; ANY_EXPLICIT=1;; --pio) DO_PIO=1; ANY_EXPLICIT=1;; --terraform) DO_TERRAFORM=1; ANY_EXPLICIT=1;; --buf) DO_BUF=1; ANY_EXPLICIT=1;;
  --check) CHECK_ONLY=1;; --no-sudo) NO_SUDO=1;; --help|-h) print_help; exit 0;; *) log_err "Flag desconocido: $1"; print_help; exit 2;; esac; shift; done
if [ "$ANY_EXPLICIT" -eq 0 ] && [ "$CHECK_ONLY" -eq 0 ]; then DO_DOTNET=1; DO_PYTHON=1; DO_NODE=1; DO_CPP=1; DO_PIO=1; DO_TERRAFORM=1; DO_BUF=1; fi
if [ "$NO_SUDO" -eq 1 ]; then has_sudo(){ false; }; run_sudo(){ log_err "sudo deshabilitado con --no-sudo"; return 1; }; fi
OS="$(detect_os)"; DISTRO="$(detect_distro)"
log_step "Conjunto Inteligente · Bootstrap host"; log_info "OS detectado: $OS"; [ "$OS" = linux ] && log_info "Distro detectada: $DISTRO"; log_info "Directorio raíz: $ROOT_DIR"
[ "$OS" = unknown ] && { log_err "Sistema operativo no soportado: $(uname -s)"; exit 3; }
if [ "$CHECK_ONLY" -eq 1 ]; then exec "$SCRIPT_DIR/verify.sh"; fi
acquire_lock || exit 1
FAILED=()
run_installer(){ local name="$1" script="$2"; log_step "Instalando $name"; if bash "$script"; then log_ok "$name completado"; else log_err "$name falló"; FAILED+=("$name"); fi; }
[ "$DO_DOTNET" -eq 1 ] && run_installer dotnet "$SCRIPT_DIR/install/dotnet.sh"
[ "$DO_PYTHON" -eq 1 ] && run_installer python "$SCRIPT_DIR/install/python.sh"
[ "$DO_NODE" -eq 1 ] && run_installer node "$SCRIPT_DIR/install/node.sh"
[ "$DO_CPP" -eq 1 ] && run_installer cpp-deps "$SCRIPT_DIR/install/cpp-deps.sh"
[ "$DO_PIO" -eq 1 ] && run_installer platformio "$SCRIPT_DIR/install/platformio.sh"
[ "$DO_TERRAFORM" -eq 1 ] && run_installer terraform "$SCRIPT_DIR/install/terraform.sh"
[ "$DO_BUF" -eq 1 ] && run_installer buf "$SCRIPT_DIR/install/buf.sh"
log_step "Verificación"; "$SCRIPT_DIR/verify.sh" || VERIFY_RC=$?; VERIFY_RC=${VERIFY_RC:-0}
if [ "${#FAILED[@]}" -gt 0 ]; then log_err "Instaladores fallidos: ${FAILED[*]}"; exit 4; fi
if [ "$VERIFY_RC" -ne 0 ]; then log_err "La verificación final reportó fallos."; exit "$VERIFY_RC"; fi
log_step "Listo"; cat <<EOF2
Próximos pasos:
  1. Recarga tu shell.
  2. cp .env.example .env
  3. docker compose up -d
  4. dotnet build ConjuntoInteligente.sln
EOF2
