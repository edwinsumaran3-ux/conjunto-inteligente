#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/common.sh"
REQUIRED=1.7.0; OS="$(detect_os)"; DISTRO="$(detect_distro)"
if command_exists terraform; then VER="$(extract_version "$(terraform version | head -n1)")"; if version_ge "$VER" "$REQUIRED"; then log_ok "Terraform $VER ya instalado"; exit 0; fi; fi
install_binary(){ local arch="$(uname -m)" osname=linux tmp; case "$arch" in x86_64) arch=amd64;; arm64|aarch64) arch=arm64;; *) log_err "Arquitectura no soportada: $arch"; return 1;; esac; [ "$OS" = macos ] && osname=darwin; tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' RETURN; download "https://releases.hashicorp.com/terraform/${REQUIRED}/terraform_${REQUIRED}_${osname}_${arch}.zip" "$tmp/terraform.zip"; if command_exists unzip; then unzip -q "$tmp/terraform.zip" -d "$tmp"; else python3 -c 'import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$tmp/terraform.zip" "$tmp"; fi; if [ -w /usr/local/bin ]; then install -m 0755 "$tmp/terraform" /usr/local/bin/terraform; else run_sudo install -m 0755 "$tmp/terraform" /usr/local/bin/terraform; fi; }
case "$OS-$DISTRO" in
 linux-ubuntu|linux-debian|linux-linuxmint|linux-pop) run_sudo apt-get update -qq; run_sudo apt-get install -y -qq gnupg software-properties-common curl lsb-release; curl -fsSL https://apt.releases.hashicorp.com/gpg | run_sudo gpg --dearmor --yes -o /usr/share/keyrings/hashicorp-archive-keyring.gpg; echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(. /etc/os-release; echo "$VERSION_CODENAME") main" | run_sudo tee /etc/apt/sources.list.d/hashicorp.list >/dev/null; run_sudo apt-get update -qq; run_sudo apt-get install -y -qq terraform;;
 linux-fedora|linux-rhel|linux-centos|linux-rocky) run_sudo dnf install -y dnf-plugins-core; run_sudo dnf config-manager --add-repo https://rpm.releases.hashicorp.com/fedora/hashicorp.repo; run_sudo dnf install -y terraform;;
 linux-arch|linux-manjaro) run_sudo pacman -Sy --noconfirm terraform;;
 macos-*) command_exists brew || { log_err 'Homebrew requerido'; exit 1; }; brew tap hashicorp/tap; brew install hashicorp/tap/terraform;;
 *) install_binary;; esac
command_exists terraform || { log_err 'terraform no disponible'; exit 1; }; VER="$(extract_version "$(terraform version | head -n1)")"; version_ge "$VER" "$REQUIRED" || { log_err "Terraform $VER < $REQUIRED"; exit 1; }; log_ok "Terraform $VER instalado"
