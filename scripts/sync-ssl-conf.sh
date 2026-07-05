#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

require_command envsubst

template_file="$SGDEV_INFRA_ROOT/proxy/nginx/templates/ssl.conf.template"
target_file="$SGDEV_INFRA_ROOT/proxy/nginx/conf.d/ssl.conf"

[[ -f "$template_file" ]] || die "SSL template not found: $template_file"

domains=("$@")
cert_name=""

if [[ ${#domains[@]} -eq 0 ]]; then
  if [[ ! -f "$target_file" ]]; then
    log "No existing SSL config found; skipping HTTPS sync"
    exit 0
  fi

  server_names_line="$(
    sed -n 's/^[[:space:]]*server_name[[:space:]]\+\(.*\);[[:space:]]*$/\1/p' "$target_file" | head -n 1
  )"
  # shellcheck disable=SC2206
  domains=($server_names_line)

  cert_name="$(
    sed -n 's#^[[:space:]]*ssl_certificate[[:space:]]\+/etc/letsencrypt/live/\([^/]*\)/fullchain.pem;.*#\1#p' "$target_file" | head -n 1
  )"
fi

[[ ${#domains[@]} -gt 0 ]] || die "Unable to detect SSL domains from $target_file"

primary_domain="${cert_name:-${domains[0]}}"
cert_file="/etc/letsencrypt/live/$primary_domain/fullchain.pem"
key_file="/etc/letsencrypt/live/$primary_domain/privkey.pem"

if [[ ! -f "$cert_file" || ! -f "$key_file" ]]; then
  die "LetsEncrypt files not found for $primary_domain"
fi

export SERVER_NAMES="${domains[*]}"
export CERT_NAME="$primary_domain"

tmp_file="$(mktemp)"
envsubst '${SERVER_NAMES} ${CERT_NAME}' < "$template_file" > "$tmp_file"

if [[ -f "$target_file" ]] && cmp -s "$tmp_file" "$target_file"; then
  rm -f "$tmp_file"
  log "SSL config already up to date for: ${domains[*]}"
  exit 0
fi

mkdir -p "$(dirname "$target_file")"
if [[ -f "$target_file" ]]; then
  cp "$target_file" "$target_file.bak-$(date +%Y%m%d%H%M%S)"
fi
mv "$tmp_file" "$target_file"

log "SSL config synced for: ${domains[*]}"
