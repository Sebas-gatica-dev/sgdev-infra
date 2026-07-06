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

Optional environment:
  APP_NAME, APP_ID, APP_DOMAIN, APP_ROOT, GIT_REMOTE_URL, BRANCH
  COMPOSE_FILES, STRIP_PREFIX, CLIENT_MAX_BODY_SIZE, PROXY_*_TIMEOUT
  BACKUP_DIR, BACKUP_COMMAND, BACKUP_VOLUMES, BACKUP_PATHS
  DB_EXCEL_ENGINE, DB_EXCEL_SERVICE, DB_EXCEL_DATABASE, DB_EXCEL_USER
  DB_EXCEL_APP_ID_COLUMN, APP_NEW_CLONE=true
USAGE
}

[[ $# -ge 3 ]] || { usage; exit 1; }

slug="$1"
repo_dir="$2"
upstream="$3"
app_path="${4:-/$slug}"
compose_file="${5:-compose.yml}"
env_file="${6:-.env}"
app_root="${APP_ROOT:-$SGDEV_APPS_ROOT/$slug}"
app_name="${APP_NAME:-}"
app_id="${APP_ID:-app_${slug//-/_}}"
app_domain="${APP_DOMAIN:-}"
git_remote_url="${GIT_REMOTE_URL:-}"
branch="${BRANCH:-main}"
compose_files="${COMPOSE_FILES:-$compose_file}"
strip_prefix="${STRIP_PREFIX:-true}"
client_max_body_size="${CLIENT_MAX_BODY_SIZE:-25m}"
proxy_connect_timeout="${PROXY_CONNECT_TIMEOUT:-10s}"
proxy_read_timeout="${PROXY_READ_TIMEOUT:-120s}"
proxy_send_timeout="${PROXY_SEND_TIMEOUT:-120s}"
backup_dir="${BACKUP_DIR:-$SGDEV_BACKUPS_ROOT/$slug}"

ensure_slug "$slug"
[[ "$app_path" == /* ]] || die "app-path must start with /"
[[ "$app_path" != "/" ]] || die "app-path cannot be / for a multiproject proxy"

write_env_var() {
  local key="$1"
  local value="$2"
  [[ -n "$value" ]] || return 0
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//\$/\\$}"
  value="${value//\`/\\\`}"
  printf '%s="%s"\n' "$key" "$value"
}

mkdir -p "$SGDEV_APPS_CONFIG_DIR" "$app_root"
config_file="$SGDEV_APPS_CONFIG_DIR/$slug.env"
[[ ! -e "$config_file" ]] || die "Config already exists: $config_file"

if [[ "${APP_NEW_CLONE:-false}" == "true" ]]; then
  [[ -n "$git_remote_url" ]] || die "GIT_REMOTE_URL is required when APP_NEW_CLONE=true"
  require_command git
  if [[ -d "$repo_dir/.git" ]]; then
    log "Repository already exists: $repo_dir"
  else
    if [[ -e "$repo_dir" ]] && [[ -n "$(find "$repo_dir" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
      die "Repo dir exists and is not empty: $repo_dir"
    fi
    mkdir -p "$(dirname "$repo_dir")"
    log "Cloning $git_remote_url into $repo_dir"
    git clone --branch "$branch" "$git_remote_url" "$repo_dir"
  fi
else
  mkdir -p "$repo_dir"
fi

{
  write_env_var APP_SLUG "$slug"
  write_env_var APP_NAME "$app_name"
  write_env_var APP_ID "$app_id"
  write_env_var APP_DOMAIN "$app_domain"
  write_env_var APP_PATH "$app_path"
  write_env_var APP_UPSTREAM "$upstream"
  write_env_var APP_ROOT "$app_root"
  write_env_var REPO_DIR "$repo_dir"
  write_env_var GIT_REMOTE_URL "$git_remote_url"
  if [[ -n "${COMPOSE_FILES:-}" || "$compose_file" =~ [[:space:]] ]]; then
    write_env_var COMPOSE_FILES "$compose_files"
  else
    write_env_var COMPOSE_FILE "$compose_file"
  fi
  write_env_var ENV_FILE "$env_file"
  write_env_var BRANCH "$branch"
  write_env_var STRIP_PREFIX "$strip_prefix"
  write_env_var CLIENT_MAX_BODY_SIZE "$client_max_body_size"
  write_env_var PROXY_CONNECT_TIMEOUT "$proxy_connect_timeout"
  write_env_var PROXY_READ_TIMEOUT "$proxy_read_timeout"
  write_env_var PROXY_SEND_TIMEOUT "$proxy_send_timeout"
  write_env_var BACKUP_DIR "$backup_dir"
  write_env_var BACKUP_COMMAND "${BACKUP_COMMAND:-}"
  write_env_var BACKUP_VOLUMES "${BACKUP_VOLUMES:-}"
  write_env_var BACKUP_PATHS "${BACKUP_PATHS:-}"
  write_env_var DB_EXCEL_ENGINE "${DB_EXCEL_ENGINE:-}"
  write_env_var DB_EXCEL_SERVICE "${DB_EXCEL_SERVICE:-}"
  write_env_var DB_EXCEL_DATABASE "${DB_EXCEL_DATABASE:-}"
  write_env_var DB_EXCEL_USER "${DB_EXCEL_USER:-}"
  write_env_var DB_EXCEL_APP_ID_COLUMN "${DB_EXCEL_APP_ID_COLUMN:-}"
  cat <<'EOF'

# Optional database Excel export/import.
# DB_EXCEL_ENGINE=postgres
# DB_EXCEL_SERVICE=db
# DB_EXCEL_DATABASE=app
# DB_EXCEL_USER=app
# DB_EXCEL_APP_ID_COLUMN=app_id
EOF
} > "$config_file"

log "Created $config_file"
"$SCRIPT_DIR/app-render-nginx.sh" "$slug"
log "Review the config, then run: ./scripts/app-deploy.sh $slug"
