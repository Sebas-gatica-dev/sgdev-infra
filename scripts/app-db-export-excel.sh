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
  ./scripts/app-db-export-excel.sh <slug> [output.xlsx] [--tables table1,table2]

Exports database rows for one project to an .xlsx workbook.

Config knobs in /etc/sgdev-infra/apps/<slug>.env:
  DB_EXCEL_ENGINE=postgres|mysql
  DB_EXCEL_SERVICE=db
  DB_EXCEL_DATABASE=app
  DB_EXCEL_USER=app
  DB_EXCEL_TABLES="public.table_a public.table_b"
  DB_EXCEL_APP_ID_COLUMN=app_id

If APP_ID and an app_id column exist, those tables are filtered to that app.
Tables without app_id are exported completely.
USAGE
}

[[ $# -ge 1 ]] || { usage; exit 1; }

slug="$1"
shift
output=""
tables_override=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tables)
      [[ $# -ge 2 ]] || die "--tables requires a value"
      tables_override="$2"
      shift 2
      ;;
    -o|--output)
      [[ $# -ge 2 ]] || die "$1 requires a value"
      output="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$output" ]]; then
        output="$1"
        shift
      else
        die "Unknown argument: $1"
      fi
      ;;
  esac
done

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

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"
if [[ -z "$output" ]]; then
  output="$BACKUP_DIR/${APP_SLUG}-db-${timestamp}.xlsx"
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
printf 'file\ttable\tscope\n' > "$tmp_dir/tables.tsv"

tables_config="${tables_override:-$(dbx_var DB_EXCEL_TABLES DB_EXPORT_TABLES DB_TABLES 2>/dev/null || true)}"
if [[ -n "$tables_config" ]]; then
  printf '%s\n' "$tables_config" | tr ', ' '\n' | sed '/^$/d' > "$tmp_dir/table-list.txt"
elif [[ "$engine" == "postgres" ]]; then
  dbx_pg_exec "$service" "$user" "$database" > "$tmp_dir/table-list.txt" <<'SQL'
SELECT table_schema || '.' || table_name
FROM information_schema.tables
WHERE table_type = 'BASE TABLE'
  AND table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name;
SQL
else
  dbx_mysql_exec "$service" "$user" "$database" > "$tmp_dir/table-list.txt" <<'SQL'
SELECT table_name
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
SQL
fi

app_id="$(dbx_var DB_EXCEL_APP_ID DB_EXPORT_APP_ID 2>/dev/null || true)"
app_id="${app_id:-${APP_ID:-}}"
app_id_column="$(dbx_var DB_EXCEL_APP_ID_COLUMN DB_EXPORT_APP_ID_COLUMN 2>/dev/null || true)"
app_id_column="${app_id_column:-app_id}"

counter=0
while IFS= read -r table_name; do
  [[ -n "$table_name" ]] || continue
  counter=$((counter + 1))
  file_id="$(printf 't%03d' "$counter")"
  columns_file="$tmp_dir/$file_id.columns"
  rows_file="$tmp_dir/$file_id.jsonl"
  scope="full"

  if [[ "$engine" == "postgres" ]]; then
    IFS=$'\t' read -r schema_name relation_name < <(dbx_table_parts "$table_name" "public")
    schema_lit="$(dbx_sql_literal "$schema_name")"
    table_lit="$(dbx_sql_literal "$relation_name")"
    dbx_pg_exec "$service" "$user" "$database" > "$columns_file" <<SQL
SELECT column_name
FROM information_schema.columns
WHERE table_schema = $schema_lit
  AND table_name = $table_lit
ORDER BY ordinal_position;
SQL
    where_sql=""
    if [[ -n "$app_id" ]] && grep -Fxq "$app_id_column" "$columns_file"; then
      scope="app_id:$app_id_column"
      where_sql=" WHERE $(dbx_pg_ident "$app_id_column")::text = $(dbx_sql_literal "$app_id")"
    fi
    table_ref="$(dbx_pg_table_ref "$table_name")"
    dbx_pg_exec "$service" "$user" "$database" > "$rows_file" <<SQL
COPY (
  SELECT row_to_json(t)
  FROM (
    SELECT *
    FROM $table_ref$where_sql
  ) t
) TO STDOUT;
SQL
  else
    default_schema="__current__"
    IFS=$'\t' read -r schema_name relation_name < <(dbx_table_parts "$table_name" "$default_schema")
    if [[ "$schema_name" == "$default_schema" ]]; then
      schema_expr="DATABASE()"
    else
      schema_expr="$(dbx_sql_literal "$schema_name")"
    fi
    table_lit="$(dbx_sql_literal "$relation_name")"
    dbx_mysql_exec "$service" "$user" "$database" > "$columns_file" <<SQL
SELECT column_name
FROM information_schema.columns
WHERE table_schema = $schema_expr
  AND table_name = $table_lit
ORDER BY ordinal_position;
SQL
    where_sql=""
    if [[ -n "$app_id" ]] && grep -Fxq "$app_id_column" "$columns_file"; then
      scope="app_id:$app_id_column"
      where_sql=" WHERE CAST($(dbx_mysql_ident "$app_id_column") AS CHAR) = $(dbx_sql_literal "$app_id")"
    fi
    json_args=""
    while IFS= read -r column_name; do
      [[ -n "$column_name" ]] || continue
      if [[ -n "$json_args" ]]; then
        json_args+=", "
      fi
      json_args+="$(dbx_sql_literal "$column_name"), $(dbx_mysql_ident "$column_name")"
    done < "$columns_file"
    table_ref="$(dbx_mysql_table_ref "$table_name")"
    if [[ -n "$json_args" ]]; then
      dbx_mysql_exec "$service" "$user" "$database" > "$rows_file" <<SQL
SELECT JSON_OBJECT($json_args)
FROM $table_ref$where_sql;
SQL
    else
      : > "$rows_file"
    fi
  fi

  printf '%s\t%s\t%s\n' "$file_id" "$table_name" "$scope" >> "$tmp_dir/tables.tsv"
  log "Prepared Excel sheet for $table_name ($scope)"
done < "$tmp_dir/table-list.txt"

"$python_bin" "$SCRIPT_DIR/app-db-excel.py" pack \
  --workdir "$tmp_dir" \
  --output "$output" \
  --app-slug "$APP_SLUG" \
  --app-id "${app_id:-}" \
  --engine "$engine" \
  --database "$database" \
  --service "$service" >/dev/null

log "Database Excel export completed: $output"
