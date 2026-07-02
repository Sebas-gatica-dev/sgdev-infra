#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ $# -eq 1 ]] || die "Usage: ./scripts/app-render-nginx.sh <slug>"

require_command envsubst

slug="$1"
load_app_config "$slug"

mkdir -p "$NGINX_APP_LOCATIONS_DIR"

upstream="${APP_UPSTREAM%/}"
case "${STRIP_PREFIX,,}" in
  true|yes|1)
    NGINX_PROXY_PASS="$upstream/"
    ;;
  false|no|0)
    NGINX_PROXY_PASS="$upstream"
    ;;
  *)
    die "STRIP_PREFIX must be true or false"
    ;;
esac
export APP_SLUG APP_PATH NGINX_PROXY_PASS CLIENT_MAX_BODY_SIZE PROXY_CONNECT_TIMEOUT PROXY_READ_TIMEOUT PROXY_SEND_TIMEOUT

template="$SGDEV_INFRA_ROOT/proxy/nginx/templates/location.conf.template"
output="$NGINX_APP_LOCATIONS_DIR/$APP_SLUG.conf"
tmp="$output.tmp"

envsubst '${APP_SLUG} ${APP_PATH} ${NGINX_PROXY_PASS} ${CLIENT_MAX_BODY_SIZE} ${PROXY_CONNECT_TIMEOUT} ${PROXY_READ_TIMEOUT} ${PROXY_SEND_TIMEOUT}' \
  < "$template" > "$tmp"
mv "$tmp" "$output"

log "Rendered Nginx location: $output"

