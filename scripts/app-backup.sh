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
logical_backup_done="false"

if [[ -n "${BACKUP_COMMAND:-}" ]]; then
  log "Running custom backup command for $APP_SLUG"
  (
    cd "$REPO_DIR"
    bash -lc "$BACKUP_COMMAND"
  )
fi

if [[ -n "${DB_EXCEL_ENGINE:-}" && -n "${DB_EXCEL_SERVICE:-}" && -n "${DB_EXCEL_DATABASE:-}" && -n "${DB_EXCEL_USER:-}" ]]; then
  compose_args="$(compose_base_args)"
  case "${DB_EXCEL_ENGINE,,}" in
    postgres|postgresql)
      db_backup_file="$BACKUP_DIR/${APP_SLUG}-postgres-${timestamp}.dump"
      db_backup_tmp="$db_backup_file.tmp"
      log "Creating logical PostgreSQL backup from $DB_EXCEL_SERVICE"
      # shellcheck disable=SC2086
      if docker compose $compose_args exec -T "$DB_EXCEL_SERVICE" sh -lc \
        'PGPASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:-}}" exec pg_dump -U "$1" -d "$2" -Fc' \
        sh "$DB_EXCEL_USER" "$DB_EXCEL_DATABASE" > "$db_backup_tmp"; then
        mv "$db_backup_tmp" "$db_backup_file"
        logical_backup_done="true"
      else
        rm -f "$db_backup_tmp"
        die "PostgreSQL backup failed for $APP_SLUG"
      fi
      ;;
    mysql|mariadb)
      db_backup_file="$BACKUP_DIR/${APP_SLUG}-mysql-${timestamp}.sql.gz"
      db_backup_tmp="$db_backup_file.tmp"
      log "Creating logical MySQL backup from $DB_EXCEL_SERVICE"
      # shellcheck disable=SC2086
      if docker compose $compose_args exec -T "$DB_EXCEL_SERVICE" sh -lc \
        'exec mysqldump -u "$1" -p"${MYSQL_PASSWORD:-${MARIADB_PASSWORD:-}}" "$2"' \
        sh "$DB_EXCEL_USER" "$DB_EXCEL_DATABASE" | gzip -c > "$db_backup_tmp"; then
        mv "$db_backup_tmp" "$db_backup_file"
        logical_backup_done="true"
      else
        rm -f "$db_backup_tmp"
        die "MySQL backup failed for $APP_SLUG"
      fi
      ;;
  esac
fi

if [[ -n "${BACKUP_VOLUMES:-}" ]]; then
  read -r -a backup_volumes_array <<< "$BACKUP_VOLUMES"
  for volume in "${backup_volumes_array[@]}"; do
    log "Backing up Docker volume $volume"
    docker run --rm \
      -v "$volume:/volume:ro" \
      -v "$BACKUP_DIR:/backup" \
      alpine:3.20 \
      tar -czf "/backup/${APP_SLUG}-${volume}-${timestamp}.tar.gz" -C /volume .
  done
fi

if [[ -n "${BACKUP_PATHS:-}" ]]; then
  read -r -a backup_paths_array <<< "$BACKUP_PATHS"
  for path in "${backup_paths_array[@]}"; do
    path_abs="$(abs_path "$REPO_DIR" "$path")"
    [[ -e "$path_abs" ]] || die "Backup path does not exist: $path_abs"
    safe_name="$(basename "$path_abs" | tr -c 'A-Za-z0-9._-' '_')"
    log "Backing up path $path_abs"
    tar -czf "$BACKUP_DIR/${APP_SLUG}-${safe_name}-${timestamp}.tar.gz" -C "$(dirname "$path_abs")" "$(basename "$path_abs")"
  done
fi

if [[ "$logical_backup_done" != "true" && -z "${BACKUP_COMMAND:-}" && -z "${BACKUP_VOLUMES:-}" && -z "${BACKUP_PATHS:-}" ]]; then
  die "No BACKUP_COMMAND, BACKUP_VOLUMES or BACKUP_PATHS configured for $APP_SLUG"
fi

log "Backup completed in $BACKUP_DIR"

