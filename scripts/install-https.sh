#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

usage() {
  cat <<'USAGE'
Usage:
  sudo ./scripts/install-https.sh <email> <domain> [extra-domain...]

Example:
  sudo ./scripts/install-https.sh sebasdeveloperlife@gmail.com sgdev.com.ar www.sgdev.com.ar
USAGE
}

[[ $# -ge 2 ]] || { usage; exit 1; }

email="$1"
shift
domains=("$@")
primary_domain="${domains[0]}"

require_command docker

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y certbot gettext-base
require_command envsubst

mkdir -p "$SGDEV_INFRA_ROOT/proxy/www/.well-known/acme-challenge"

"$SCRIPT_DIR/proxy-up.sh"

domain_args=()
for domain in "${domains[@]}"; do
  domain_args+=("-d" "$domain")
done

certbot certonly \
  --webroot \
  --webroot-path "$SGDEV_INFRA_ROOT/proxy/www" \
  --email "$email" \
  --agree-tos \
  --non-interactive \
  --keep-until-expiring \
  "${domain_args[@]}"

export SERVER_NAMES="${domains[*]}"
export CERT_NAME="$primary_domain"

"$SCRIPT_DIR/sync-ssl-conf.sh" "${domains[@]}"

"$SCRIPT_DIR/proxy-reload.sh"

cat >/etc/cron.d/sgdev-certbot-renew <<EOF
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
17 3 * * * root certbot renew --quiet --deploy-hook 'cd $SGDEV_INFRA_ROOT && ./scripts/proxy-reload.sh'
EOF

log "HTTPS ready for: ${domains[*]}"
