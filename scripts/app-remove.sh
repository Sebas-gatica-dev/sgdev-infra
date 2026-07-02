#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/app-remove.sh <slug> [--stop]

Removes the Nginx route. It does not delete the repo, env file, volumes or data.
With --stop it also runs docker compose down for the app.
USAGE
}

[[ $# -ge 1 ]] || { usage; exit 1; }

slug="$1"
stop_app="${2:-}"
load_app_config "$slug"

if [[ "$stop_app" == "--stop" ]]; then
  "$SCRIPT_DIR/app-stop.sh" "$APP_SLUG"
fi

rm -f "$NGINX_APP_LOCATIONS_DIR/$APP_SLUG.conf"
log "Removed Nginx route for $APP_SLUG"

if docker compose -f "$PROXY_COMPOSE_FILE" ps --status running | grep -q 'sgdev-proxy-nginx'; then
  "$SCRIPT_DIR/proxy-reload.sh"
fi

