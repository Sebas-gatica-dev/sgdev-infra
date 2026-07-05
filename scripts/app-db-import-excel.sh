#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"
# shellcheck source=lib-db-excel.sh
source "$SCRIPT_DIR/lib-db-excel.sh"

usage() {
  cat <<'USAGE'
Usage:
  ./scripts/app-db-import-excel.sh <slug> <file.xlsx> [--mode insert|replace-project] [--allow-cross-app]

Imports a workbook previously created by app-db-export-excel.sh.

Modes:
  insert           Insert workbook rows. Existing primary keys can conflict.
  replace-project Delete rows with APP_ID/DB_EXCEL_APP_ID from tables that have
                  DB_EXCEL_APP_ID_COLUMN, then insert workbook rows.

The workbook app_slug/app_id must match the target project unless
--allow-cross-app is passed explicitly.
USAGE
}

[[ $# -ge 2 ]] || { usage; exit 1; }

slug="$1"
input="$2"
shift 2
mode="insert"
allow_cross_app="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      [[ $# -ge 2 ]] || die "--mode requires a value"
      mode="$2"
      shift 2
      ;;
    --allow-cross-app)
      allow_cross_app="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

case "$mode" in
  insert|replace-project) ;;
  *) die "Invalid mode: $mode" ;;
esac

[[ -f "$input" ]] || die "Excel file not found: $input"

load_app_config "$slug"
require_command docker
python_bin="$(dbx_python)"
DBX_COMPOSE_ARGS="$(compose_base_args)"

service="$(dbx_detect_service)"
engine="$(dbx_detect_engine "$service")"
if [[ "$engine" == "postgres" ]]; then
  user="$(dbx_detect_postgres_user "$service")"
  database="$(dbx_detect_postgres_database "$service" "$user")"
else
  user="$(dbx_detect_mysql_user "$service")"
  database="$(dbx_detect_mysql_database "$service")"
fi

app_id="$(dbx_var DB_EXCEL_APP_ID DB_IMPORT_APP_ID 2>/dev/null || true)"
app_id="${app_id:-${APP_ID:-}}"
app_id_column="$(dbx_var DB_EXCEL_APP_ID_COLUMN DB_IMPORT_APP_ID_COLUMN 2>/dev/null || true)"
app_id_column="${app_id_column:-app_id}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

unpack_args=(
  "$SCRIPT_DIR/app-db-excel.py" unpack
  --input "$input"
  --workdir "$tmp_dir"
  --app-slug "$APP_SLUG"
  --app-id "${app_id:-}"
)
if [[ "$allow_cross_app" == "true" ]]; then
  unpack_args+=(--allow-cross-app)
fi
"$python_bin" "${unpack_args[@]}" >/dev/null

"$python_bin" "$SCRIPT_DIR/app-db-excel.py" sql \
  --workdir "$tmp_dir" \
  --output "$tmp_dir/import.sql" \
  --dialect "$engine" \
  --mode "$mode" \
  --app-id "${app_id:-}" \
  --app-id-column "$app_id_column" >/dev/null

log "Importing $input into $engine database $database through service $service"
if [[ "$engine" == "postgres" ]]; then
  dbx_pg_exec "$service" "$user" "$database" < "$tmp_dir/import.sql"
else
  dbx_mysql_exec "$service" "$user" "$database" < "$tmp_dir/import.sql"
fi

log "Database Excel import completed for $APP_SLUG"
