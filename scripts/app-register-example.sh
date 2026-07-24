#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ $# -eq 1 ]] || die "Usage: ./scripts/app-register-example.sh <slug>"

slug="$1"
ensure_slug "$slug"

example_file="$SGDEV_INFRA_ROOT/examples/apps/$slug.env.example"
config_file="$SGDEV_APPS_CONFIG_DIR/$slug.env"

[[ -f "$example_file" ]] || die "Versioned app example not found: $example_file"
[[ ! -e "$config_file" ]] || die "App config already exists: $config_file"

# Examples are trusted, version-controlled deployment manifests. Validate the
# minimum contract before installing one as live configuration.
set -a
# shellcheck disable=SC1090
source "$example_file"
set +a

[[ "${APP_SLUG:-}" == "$slug" ]] || die "APP_SLUG in $example_file must be $slug"
[[ "${APP_ROOT:-}" == "$SGDEV_APPS_ROOT/$slug" ]] || die "APP_ROOT must be $SGDEV_APPS_ROOT/$slug"
[[ "${REPO_DIR:-}" == "$SGDEV_APPS_ROOT/$slug/repo" ]] || die "REPO_DIR must stay in the app root"
[[ "${APP_PATH:-}" == /* && "${APP_PATH:-}" != "/" ]] || die "APP_PATH must be a non-root path"
[[ "${APP_UPSTREAM:-}" == http://"$slug"-* ]] || die "APP_UPSTREAM must target a $slug-* service"
[[ -n "${GIT_REMOTE_URL:-}" ]] || die "GIT_REMOTE_URL is required"

install -d -m 0755 "$SGDEV_APPS_CONFIG_DIR"
install -m 0600 "$example_file" "$config_file"
log "Registered $slug from $example_file"
