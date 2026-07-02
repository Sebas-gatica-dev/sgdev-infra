#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

require_command docker

log "Testing Nginx config"
docker compose -f "$PROXY_COMPOSE_FILE" exec -T nginx nginx -t

log "Reloading Nginx"
docker compose -f "$PROXY_COMPOSE_FILE" exec -T nginx nginx -s reload

