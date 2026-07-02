#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

if [[ $# -eq 0 ]]; then
  log "Proxy"
  docker compose -f "$PROXY_COMPOSE_FILE" ps || true
  echo
  log "Registered apps"
  if compgen -G "$SGDEV_APPS_CONFIG_DIR/*.env" >/dev/null; then
    for file in "$SGDEV_APPS_CONFIG_DIR"/*.env; do
      basename "$file" .env
    done
  else
    echo "No apps registered in $SGDEV_APPS_CONFIG_DIR"
  fi
  exit 0
fi

slug="$1"
load_app_config "$slug"
compose_args="$(compose_base_args)"

log "Compose status for $APP_SLUG"
# shellcheck disable=SC2086
docker compose $compose_args ps

echo
log "Route"
printf '%s -> %s\n' "$APP_PATH/" "$APP_UPSTREAM"

