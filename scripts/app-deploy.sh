#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/app-deploy.sh <slug> [--no-pull]

Deploys one app:
  - clones the repo if GIT_REMOTE_URL is configured and repo is missing
  - pulls the configured branch unless --no-pull is passed
  - runs docker compose up -d --build
  - renders and reloads the shared Nginx route
USAGE
}

[[ $# -ge 1 ]] || { usage; exit 1; }

slug="$1"
no_pull="false"
if [[ "${2:-}" == "--no-pull" ]]; then
  no_pull="true"
fi

load_app_config "$slug"
require_command docker
require_command git
require_command flock

lock_file="/tmp/sgdev-deploy-$APP_SLUG.lock"
exec 9>"$lock_file"
flock -n 9 || die "Deploy already running for $APP_SLUG"

mkdir -p "$APP_ROOT" "$BACKUP_DIR"

if [[ ! -d "$REPO_DIR/.git" ]]; then
  [[ -n "${GIT_REMOTE_URL:-}" ]] || die "Repo missing and GIT_REMOTE_URL is not configured: $REPO_DIR"
  log "Cloning $GIT_REMOTE_URL into $REPO_DIR"
  git clone --branch "$BRANCH" "$GIT_REMOTE_URL" "$REPO_DIR"
elif [[ "$no_pull" != "true" ]]; then
  log "Pulling latest $BRANCH in $REPO_DIR"
  git -C "$REPO_DIR" fetch origin "$BRANCH"
  git -C "$REPO_DIR" checkout "$BRANCH"
  git -C "$REPO_DIR" pull --ff-only origin "$BRANCH"
fi

compose_args="$(compose_base_args)"
log "Validating Docker Compose configuration"
# shellcheck disable=SC2086
docker compose $compose_args config --quiet

reject_public_ports="${REJECT_PUBLIC_PORTS:-false}"
case "${reject_public_ports,,}" in
  true|yes|1)
    require_command python3
    log "Checking that the app does not publish public host ports"
    # shellcheck disable=SC2086
    docker compose $compose_args config --format json | python3 -c '
import json
import sys

config = json.load(sys.stdin)
violations = []
for service_name, service in (config.get("services") or {}).items():
    for port in service.get("ports") or []:
        published = port.get("published")
        if published in (None, ""):
            continue
        host_ip = str(port.get("host_ip") or "")
        if host_ip not in {"127.0.0.1", "::1"}:
            violations.append("{}:{}->{}".format(service_name, published, port.get("target")))
if violations:
    print("Public host ports are forbidden; route traffic through sgdev-proxy: " + ", ".join(violations), file=sys.stderr)
    raise SystemExit(1)
'
    ;;
  false|no|0)
    ;;
  *)
    die "REJECT_PUBLIC_PORTS must be true or false"
    ;;
esac

docker network inspect "$PROXY_NETWORK" >/dev/null 2>&1 || docker network create "$PROXY_NETWORK"

log "Deploying $APP_SLUG with Docker Compose"
# shellcheck disable=SC2086
docker compose $compose_args up -d --build

if docker compose $compose_args config --services | grep -qx 'nginx'; then
  log "Restarting app nginx so upstream container DNS is fresh"
  # shellcheck disable=SC2086
  docker compose $compose_args restart nginx
fi

"$SCRIPT_DIR/app-render-nginx.sh" "$APP_SLUG"

if docker compose -f "$PROXY_COMPOSE_FILE" ps --status running | grep -q 'sgdev-proxy-nginx'; then
  "$SCRIPT_DIR/proxy-reload.sh"
else
  "$SCRIPT_DIR/proxy-up.sh"
fi

log "Done: $APP_PATH/"
