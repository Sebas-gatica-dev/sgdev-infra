#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

env_file="${SHARED_DB_ENV_FILE:-$SGDEV_CONFIG_DIR/shared-db.env}"
compose_file="$SGDEV_INFRA_ROOT/services/shared-db/compose.yml"

[[ -f "$env_file" ]] || die "Shared DB env file not found: $env_file. Copy services/shared-db/.env.example and set real passwords."
[[ -f "$compose_file" ]] || die "Compose file not found: $compose_file"

require_command docker

docker network inspect "$DATA_NETWORK" >/dev/null 2>&1 || docker network create "$DATA_NETWORK"

log "Starting shared PostgreSQL pgvector service"
docker compose \
  --project-directory "$SGDEV_INFRA_ROOT/services/shared-db" \
  --env-file "$env_file" \
  -f "$compose_file" \
  up -d

log "Shared DB is available inside Docker as sgdev-postgres:5432 on $DATA_NETWORK"
