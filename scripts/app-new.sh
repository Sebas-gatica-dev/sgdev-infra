#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

usage() {
  cat <<'USAGE'
Usage:
  sudo ./scripts/app-new.sh <slug> <repo-dir> <upstream-url> [app-path] [compose-file] [env-file]

Example:
  sudo ./scripts/app-new.sh janoai /opt/apps/janoai/repo http://janoai-nginx:80 /janoai compose.prod.yml .env.production
USAGE
}

[[ $# -ge 3 ]] || { usage; exit 1; }

slug="$1"
repo_dir="$2"
upstream="$3"
app_path="${4:-/$slug}"
compose_file="${5:-compose.yml}"
env_file="${6:-.env}"

ensure_slug "$slug"

mkdir -p "$SGDEV_APPS_CONFIG_DIR"
config_file="$SGDEV_APPS_CONFIG_DIR/$slug.env"
[[ ! -e "$config_file" ]] || die "Config already exists: $config_file"

cat > "$config_file" <<EOF
APP_SLUG=$slug
APP_PATH=$app_path
APP_UPSTREAM=$upstream
REPO_DIR=$repo_dir
COMPOSE_FILE=$compose_file
ENV_FILE=$env_file
BRANCH=main
STRIP_PREFIX=true
CLIENT_MAX_BODY_SIZE=25m
PROXY_READ_TIMEOUT=120s
EOF

log "Created $config_file"
"$SCRIPT_DIR/app-render-nginx.sh" "$slug"
log "Review the config, then run: ./scripts/app-deploy.sh $slug"

