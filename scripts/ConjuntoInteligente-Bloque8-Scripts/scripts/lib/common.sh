#!/usr/bin/env bash
# Utilidades compartidas por los instaladores.
# No usa set -e: cada instalador define su propia política.

if [ -t 2 ] && [ -z "${NO_COLOR:-}" ]; then
  C_RED='\033[0;31m'; C_GREEN='\033[0;32m'; C_YELLOW='\033[0;33m'; C_BLUE='\033[0;34m'; C_BOLD='\033[1m'; C_RESET='\033[0m'
else
  C_RED=''; C_GREEN=''; C_YELLOW=''; C_BLUE=''; C_BOLD=''; C_RESET=''
fi

log_info(){ printf "${C_BLUE}[INFO]${C_RESET} %s\n" "$*" >&2; }
log_ok(){ printf "${C_GREEN}[ OK ]${C_RESET} %s\n" "$*" >&2; }
log_warn(){ printf "${C_YELLOW}[WARN]${C_RESET} %s\n" "$*" >&2; }
log_err(){ printf "${C_RED}[ERR ]${C_RESET} %s\n" "$*" >&2; }
log_step(){ printf "\n${C_BOLD}▶ %s${C_RESET}\n" "$*" >&2; }

command_exists(){ command -v "$1" >/dev/null 2>&1; }
detect_os(){ case "$(uname -s)" in Linux*) echo linux;; Darwin*) echo macos;; *) echo unknown;; esac; }
detect_distro(){ if [ -r /etc/os-release ]; then . /etc/os-release; echo "${ID:-unknown}"; else echo unknown; fi; }
is_root(){ [ "$(id -u)" -eq 0 ]; }
has_sudo(){ is_root || { command_exists sudo && sudo -n true 2>/dev/null; }; }
run_sudo(){ if is_root; then "$@"; elif has_sudo; then sudo "$@"; else log_err "Se requiere sudo para: $*"; return 1; fi; }

version_ge(){
  local a b
  a="$(extract_version "$1")"; b="$(extract_version "$2")"
  [ -n "$a" ] && [ -n "$b" ] || return 1
  if command_exists sort && sort -V </dev/null >/dev/null 2>&1; then
    [ "$(printf '%s\n%s\n' "$b" "$a" | sort -V | tail -n1)" = "$a" ]
  else
    [ "$(printf '%s\n%s\n' "$b" "$a" | sort -n | tail -n1)" = "$a" ]
  fi
}
extract_version(){ printf '%s' "$1" | grep -oE '[0-9]+(\.[0-9]+){1,3}' | head -n1; }

shell_rc_file(){ case "$(basename "${SHELL:-bash}")" in zsh) echo "${ZDOTDIR:-$HOME}/.zshrc";; bash) echo "$HOME/.bashrc";; fish) echo "$HOME/.config/fish/config.fish";; *) echo "$HOME/.profile";; esac; }
ensure_path_line(){ local line="$1" rc; rc="$(shell_rc_file)"; mkdir -p "$(dirname "$rc")"; touch "$rc"; if ! grep -Fqx "$line" "$rc"; then printf '\n# Añadido por bootstrap Conjunto Inteligente\n%s\n' "$line" >> "$rc"; log_info "PATH actualizado en $rc"; fi; }

download(){ local url="$1" dest="$2"; if command_exists curl; then curl -fsSL "$url" -o "$dest"; elif command_exists wget; then wget -q "$url" -O "$dest"; else log_err "Se requiere curl o wget para descargar: $url"; return 1; fi; }

acquire_lock(){
  local lock="${TMPDIR:-/tmp}/conjunto-bootstrap.lock" pid
  if [ -f "$lock" ]; then pid="$(cat "$lock" 2>/dev/null || true)"; if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then log_err "Ya hay un bootstrap corriendo (pid=$pid)."; return 1; fi; fi
  echo "$$" > "$lock"; BOOTSTRAP_LOCK_FILE="$lock"; export BOOTSTRAP_LOCK_FILE
  trap 'rm -f "${BOOTSTRAP_LOCK_FILE:-}"' EXIT
}

pkg_config_exists(){ command_exists pkg-config; }
has_header(){ local h="$1"; [ -f "/usr/include/$h" ] || [ -f "/usr/local/include/$h" ] || [ -f "/opt/homebrew/include/$h" ] || { command_exists brew && [ -f "$(brew --prefix 2>/dev/null)/include/$h" ]; }; }
