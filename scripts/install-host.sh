#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ "${EUID:-$(id -u)}" -eq 0 ]] || die "Run with sudo: sudo ./scripts/install-host.sh"

log "Installing base packages"
apt-get update
apt-get install -y ca-certificates curl git gettext-base python3 jq util-linux ufw

if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker Engine"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc

  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list

  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  log "Docker already installed"
fi

target_user="${SUDO_USER:-}"
if [[ -n "$target_user" && "$target_user" != "root" ]]; then
  usermod -aG docker "$target_user"
  log "Added $target_user to docker group. Reconnect SSH before using docker without sudo."
fi

log "Creating host directories"
mkdir -p "$SGDEV_APPS_ROOT" "$SGDEV_BACKUPS_ROOT" /opt/secrets
mkdir -p "$SGDEV_APPS_CONFIG_DIR" "$SGDEV_CICD_CONFIG_DIR"
mkdir -p "$NGINX_APP_LOCATIONS_DIR"

if [[ -n "$target_user" && "$target_user" != "root" ]]; then
  chown -R "$target_user":"$target_user" "$SGDEV_INFRA_ROOT" "$SGDEV_APPS_ROOT" "$SGDEV_BACKUPS_ROOT"
fi

log "Creating Docker proxy network: $PROXY_NETWORK"
docker network inspect "$PROXY_NETWORK" >/dev/null 2>&1 || docker network create "$PROXY_NETWORK"

log "Opening basic firewall rules if ufw is enabled"
ufw allow OpenSSH >/dev/null || true
ufw allow 80/tcp >/dev/null || true
ufw allow 443/tcp >/dev/null || true

log "Host is ready. If your user was added to docker, reconnect SSH now."
