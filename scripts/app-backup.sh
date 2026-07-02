#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ $# -eq 1 ]] || die "Usage: ./scripts/app-backup.sh <slug>"

slug="$1"
load_app_config "$slug"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"

if [[ -n "${BACKUP_COMMAND:-}" ]]; then
  log "Running custom backup command for $APP_SLUG"
  (
    cd "$REPO_DIR"
    bash -lc "$BACKUP_COMMAND"
  )
fi

if [[ -n "${BACKUP_VOLUMES:-}" ]]; then
  for volume in $BACKUP_VOLUMES; do
    log "Backing up Docker volume $volume"
    docker run --rm \
      -v "$volume:/volume:ro" \
      -v "$BACKUP_DIR:/backup" \
      alpine:3.20 \
      tar -czf "/backup/${APP_SLUG}-${volume}-${timestamp}.tar.gz" -C /volume .
  done
fi

if [[ -n "${BACKUP_PATHS:-}" ]]; then
  for path in $BACKUP_PATHS; do
    path_abs="$(abs_path "$REPO_DIR" "$path")"
    [[ -e "$path_abs" ]] || die "Backup path does not exist: $path_abs"
    safe_name="$(basename "$path_abs" | tr -c 'A-Za-z0-9._-' '_')"
    log "Backing up path $path_abs"
    tar -czf "$BACKUP_DIR/${APP_SLUG}-${safe_name}-${timestamp}.tar.gz" -C "$(dirname "$path_abs")" "$(basename "$path_abs")"
  done
fi

if [[ -z "${BACKUP_COMMAND:-}" && -z "${BACKUP_VOLUMES:-}" && -z "${BACKUP_PATHS:-}" ]]; then
  die "No BACKUP_COMMAND, BACKUP_VOLUMES or BACKUP_PATHS configured for $APP_SLUG"
fi

log "Backup completed in $BACKUP_DIR"

