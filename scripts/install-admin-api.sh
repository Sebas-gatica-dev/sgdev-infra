#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ "${EUID:-$(id -u)}" -eq 0 ]] || die "Run with sudo: sudo ./scripts/install-admin-api.sh"
require_command python3

service_user="${1:-${SUDO_USER:-root}}"
[[ -n "$service_user" ]] || die "Could not determine service user"

env_file="$SGDEV_CONFIG_DIR/admin-api.env"
control_env_file="$SGDEV_CONFIG_DIR/admin-control-api.env"

generate_token() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
  fi
}

detect_admin_bind_host() {
  if [[ -n "${SGDEV_ADMIN_API_BIND_HOST:-}" ]]; then
    printf '%s\n' "$SGDEV_ADMIN_API_BIND_HOST"
    return
  fi

  if command -v ip >/dev/null 2>&1 && ip -4 addr show docker0 >/dev/null 2>&1; then
    ip -4 addr show docker0 \
      | awk '/inet / { sub(/\/.*/, "", $2); print $2; exit }'
    return
  fi

  printf '127.0.0.1\n'
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"

  if grep -qE "^${key}=" "$file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
  fi
}

log "Installing SGDEV admin monitor API as user: $service_user"
mkdir -p "$SGDEV_CONFIG_DIR" /var/log/sgdev-infra
admin_bind_host="$(detect_admin_bind_host)"
[[ -n "$admin_bind_host" ]] || admin_bind_host="127.0.0.1"

if [[ ! -f "$env_file" ]]; then
  token="$(generate_token)"
  cat > "$env_file" <<EOF
SGDEV_ADMIN_API_HOST=$admin_bind_host
SGDEV_ADMIN_API_PORT=9100
SGDEV_ADMIN_API_TOKEN=$token
SGDEV_INFRA_ROOT=$SGDEV_INFRA_ROOT
SGDEV_APPS_CONFIG_DIR=$SGDEV_APPS_CONFIG_DIR
SGDEV_MONITOR_DOCKER=auto
SGDEV_MONITOR_DISK_PATHS=/,/opt,/opt/apps,/opt/backups
SGDEV_MONITOR_PROCESS_LIMIT=12
SGDEV_MONITOR_PROCESS_ARGS=false
EOF
  log "Created $env_file"
else
  log "Keeping existing $env_file"
  token="$(grep -E '^SGDEV_ADMIN_API_TOKEN=' "$env_file" | tail -n 1 | cut -d= -f2- || true)"
  [[ -n "$token" ]] || token="$(generate_token)"
fi
set_env_value "$env_file" "SGDEV_ADMIN_API_HOST" "$admin_bind_host"

chown "$service_user":"$service_user" "$env_file" || true
chmod 600 "$env_file" || true
chown "$service_user":"$service_user" /var/log/sgdev-infra || true

if [[ ! -f "$control_env_file" ]]; then
  cat > "$control_env_file" <<EOF
SGDEV_ADMIN_API_HOST=$admin_bind_host
SGDEV_ADMIN_API_PORT=9101
SGDEV_ADMIN_API_MODE=local
SGDEV_ADMIN_TOKEN=$token
SGDEV_ADMIN_API_TOKEN=$token
SGDEV_REMOTE_INFRA_ROOT=$SGDEV_INFRA_ROOT
SGDEV_INFRA_ROOT=$SGDEV_INFRA_ROOT
SGDEV_APPS_CONFIG_DIR=$SGDEV_APPS_CONFIG_DIR
EOF
  log "Created $control_env_file"
else
  log "Keeping existing $control_env_file"
fi
set_env_value "$control_env_file" "SGDEV_ADMIN_API_HOST" "$admin_bind_host"

chown "$service_user":"$service_user" "$control_env_file" || true
chmod 600 "$control_env_file" || true

if command -v docker >/dev/null 2>&1 && getent group docker >/dev/null 2>&1; then
  usermod -aG docker "$service_user" || true
  log "Ensured $service_user belongs to docker group for container metrics. Restart SSH session if needed."
fi

cat > /etc/systemd/system/sgdev-admin-api.service <<EOF
[Unit]
Description=SGDEV Infra admin monitor API
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=$service_user
WorkingDirectory=$SGDEV_INFRA_ROOT
EnvironmentFile=$env_file
ExecStart=/usr/bin/python3 $SGDEV_INFRA_ROOT/admin/monitor_api.py
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sgdev-admin-api.service
systemctl restart sgdev-admin-api.service

cat > /etc/systemd/system/sgdev-admin-control-api.service <<EOF
[Unit]
Description=SGDEV Infra admin control API
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=$service_user
WorkingDirectory=$SGDEV_INFRA_ROOT
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=$control_env_file
ExecStart=/usr/bin/python3 $SGDEV_INFRA_ROOT/admin_api.py
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=$SGDEV_INFRA_ROOT /opt /var/log/sgdev-infra $SGDEV_CONFIG_DIR

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sgdev-admin-control-api.service
systemctl restart sgdev-admin-control-api.service

log "Admin monitor API installed on $admin_bind_host:9100"
log "Admin control API installed on $admin_bind_host:9101"
log "API token is stored in $env_file and $control_env_file"
systemctl --no-pager --full status sgdev-admin-api.service || true
systemctl --no-pager --full status sgdev-admin-control-api.service || true
