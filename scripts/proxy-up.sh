#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

require_command docker

docker network inspect "$PROXY_NETWORK" >/dev/null 2>&1 || docker network create "$PROXY_NETWORK"

proxy_env_file="$SGDEV_INFRA_ROOT/proxy/.env"
if [[ ! -f "$proxy_env_file" ]]; then
  proxy_env_file="$SGDEV_INFRA_ROOT/proxy/.env.example"
fi

log "Starting shared Nginx proxy"
docker compose -f "$PROXY_COMPOSE_FILE" --env-file "$proxy_env_file" up -d

log "Proxy status"
docker compose -f "$PROXY_COMPOSE_FILE" ps
