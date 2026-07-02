#!/usr/bin/env bash
set -euo pipefail

SGDEV_INFRA_ROOT="${SGDEV_INFRA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SGDEV_CONFIG_DIR="${SGDEV_CONFIG_DIR:-/etc/sgdev-infra}"
SGDEV_APPS_CONFIG_DIR="${SGDEV_APPS_CONFIG_DIR:-$SGDEV_CONFIG_DIR/apps}"
SGDEV_CICD_CONFIG_DIR="${SGDEV_CICD_CONFIG_DIR:-$SGDEV_CONFIG_DIR/cicd}"
SGDEV_APPS_ROOT="${SGDEV_APPS_ROOT:-/opt/apps}"
SGDEV_BACKUPS_ROOT="${SGDEV_BACKUPS_ROOT:-/opt/backups}"
PROXY_NETWORK="${PROXY_NETWORK:-sgdev-proxy}"
PROXY_COMPOSE_FILE="${PROXY_COMPOSE_FILE:-$SGDEV_INFRA_ROOT/proxy/compose.yml}"
NGINX_APP_LOCATIONS_DIR="${NGINX_APP_LOCATIONS_DIR:-$SGDEV_INFRA_ROOT/proxy/nginx/app-locations}"

log() {
  printf '[sgdev-infra] %s\n' "$*"
}

die() {
  printf '[sgdev-infra] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
}

ensure_slug() {
  local slug="$1"
  [[ "$slug" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || die "Invalid slug: $slug"
}

abs_path() {
  local base="$1"
  local path="$2"
  if [[ "$path" = /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s/%s\n' "$base" "$path"
  fi
}

load_app_config() {
  local slug="$1"
  ensure_slug "$slug"

  local config_file="$SGDEV_APPS_CONFIG_DIR/$slug.env"
  [[ -f "$config_file" ]] || die "App config not found: $config_file"

  # shellcheck disable=SC1090
  source "$config_file"

  APP_SLUG="${APP_SLUG:-$slug}"
  APP_ROOT="${APP_ROOT:-$SGDEV_APPS_ROOT/$APP_SLUG}"
  REPO_DIR="${REPO_DIR:-$APP_ROOT/repo}"
  COMPOSE_FILE="${COMPOSE_FILE:-compose.yml}"
  COMPOSE_FILES="${COMPOSE_FILES:-$COMPOSE_FILE}"
  ENV_FILE="${ENV_FILE:-.env}"
  APP_PATH="${APP_PATH:-/$APP_SLUG}"
  STRIP_PREFIX="${STRIP_PREFIX:-true}"
  BRANCH="${BRANCH:-main}"
  CLIENT_MAX_BODY_SIZE="${CLIENT_MAX_BODY_SIZE:-25m}"
  PROXY_CONNECT_TIMEOUT="${PROXY_CONNECT_TIMEOUT:-10s}"
  PROXY_READ_TIMEOUT="${PROXY_READ_TIMEOUT:-120s}"
  PROXY_SEND_TIMEOUT="${PROXY_SEND_TIMEOUT:-120s}"
  BACKUP_DIR="${BACKUP_DIR:-$SGDEV_BACKUPS_ROOT/$APP_SLUG}"

  [[ "$APP_SLUG" == "$slug" ]] || die "APP_SLUG must match file name: $slug"
  [[ "$APP_PATH" == /* ]] || die "APP_PATH must start with /"
  [[ "$APP_PATH" != "/" ]] || die "APP_PATH cannot be / for a multiproject proxy"
  [[ -n "${APP_UPSTREAM:-}" ]] || die "APP_UPSTREAM is required in $config_file"
}

compose_base_args() {
  local args=(--project-directory "$REPO_DIR")
  local env_file_abs
  env_file_abs="$(abs_path "$REPO_DIR" "$ENV_FILE")"
  if [[ -f "$env_file_abs" ]]; then
    args+=(--env-file "$env_file_abs")
  fi
  local compose_file compose_file_abs
  for compose_file in $COMPOSE_FILES; do
    compose_file_abs="$(abs_path "$REPO_DIR" "$compose_file")"
    [[ -f "$compose_file_abs" ]] || die "Compose file not found: $compose_file_abs"
    args+=(-f "$compose_file_abs")
  done

  printf '%q ' "${args[@]}"
}
