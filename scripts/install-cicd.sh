#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ "${EUID:-$(id -u)}" -eq 0 ]] || die "Run with sudo: sudo ./scripts/install-cicd.sh"
require_command python3

service_user="${1:-${SUDO_USER:-root}}"
[[ -n "$service_user" ]] || die "Could not determine service user"

log "Installing GitHub webhook service as user: $service_user"
mkdir -p /var/log/sgdev-infra "$SGDEV_CICD_CONFIG_DIR"
chown "$service_user":"$service_user" /var/log/sgdev-infra || true
chown "$service_user":"$service_user" "$SGDEV_CICD_CONFIG_DIR" || true
chmod 700 "$SGDEV_CICD_CONFIG_DIR" || true

cat > /etc/systemd/system/sgdev-webhookd.service <<EOF
[Unit]
Description=Sgdev Infra GitHub webhook deployer
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=$service_user
WorkingDirectory=$SGDEV_INFRA_ROOT
Environment=SGDEV_INFRA_ROOT=$SGDEV_INFRA_ROOT
Environment=SGDEV_CONFIG_DIR=$SGDEV_CONFIG_DIR
Environment=SGDEV_WEBHOOK_HOST=127.0.0.1
Environment=SGDEV_WEBHOOK_PORT=9000
Environment=SGDEV_WEBHOOK_LOG_DIR=/var/log/sgdev-infra
ExecStart=/usr/bin/python3 $SGDEV_INFRA_ROOT/cicd/webhookd.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now sgdev-webhookd.service

log "Webhook service installed"
systemctl --no-pager --full status sgdev-webhookd.service || true
