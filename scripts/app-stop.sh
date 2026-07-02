#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ $# -eq 1 ]] || die "Usage: ./scripts/app-stop.sh <slug>"

slug="$1"
load_app_config "$slug"
compose_args="$(compose_base_args)"

log "Stopping $APP_SLUG without deleting volumes"
# shellcheck disable=SC2086
docker compose $compose_args down

