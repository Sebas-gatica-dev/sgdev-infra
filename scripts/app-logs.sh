#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ $# -ge 1 ]] || die "Usage: ./scripts/app-logs.sh <slug> [service...]"

slug="$1"
shift || true
load_app_config "$slug"

compose_args="$(compose_base_args)"
# shellcheck disable=SC2086
docker compose $compose_args logs -f "$@"

