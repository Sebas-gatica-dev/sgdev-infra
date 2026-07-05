#!/usr/bin/env bash

dbx_python() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
  elif command -v python >/dev/null 2>&1; then
    printf '%s\n' "python"
  else
    die "Missing command: python3"
  fi
}

dbx_var() {
  local name
  for name in "$@"; do
    if [[ -n "${!name:-}" ]]; then
      printf '%s\n' "${!name}"
      return 0
    fi
  done
  return 1
}

dbx_sql_literal() {
  local value="${1:-}"
  value="${value//\'/\'\'}"
  printf "'%s'" "$value"
}

dbx_pg_ident() {
  local value="${1:-}"
  value="${value//\"/\"\"}"
  printf '"%s"' "$value"
}

dbx_mysql_ident() {
  local value="${1:-}"
  value="${value//\`/\`\`}"
  printf '`%s`' "$value"
}

dbx_pg_table_ref() {
  local value="$1"
  local schema table
  if [[ "$value" == *.* ]]; then
    schema="${value%%.*}"
    table="${value#*.}"
  else
    schema="public"
    table="$value"
  fi
  printf '%s.%s' "$(dbx_pg_ident "$schema")" "$(dbx_pg_ident "$table")"
}

dbx_mysql_table_ref() {
  local value="$1"
  local schema table
  if [[ "$value" == *.* ]]; then
    schema="${value%%.*}"
    table="${value#*.}"
    printf '%s.%s' "$(dbx_mysql_ident "$schema")" "$(dbx_mysql_ident "$table")"
  else
    printf '%s' "$(dbx_mysql_ident "$value")"
  fi
}

dbx_table_parts() {
  local value="$1"
  local default_schema="$2"
  if [[ "$value" == *.* ]]; then
    printf '%s\t%s\n' "${value%%.*}" "${value#*.}"
  else
    printf '%s\t%s\n' "$default_schema" "$value"
  fi
}

dbx_compose_exec() {
  local service="$1"
  shift
  # shellcheck disable=SC2086
  docker compose $DBX_COMPOSE_ARGS exec -T "$service" "$@"
}

dbx_container_env() {
  local service="$1"
  local key="$2"
  dbx_compose_exec "$service" sh -lc 'printenv "$1" 2>/dev/null || true' sh "$key" | tr -d '\r'
}

dbx_has_command() {
  local service="$1"
  local command_name="$2"
  dbx_compose_exec "$service" sh -lc 'command -v "$1" >/dev/null 2>&1' sh "$command_name" >/dev/null 2>&1
}

dbx_first_existing_service() {
  local service candidate
  local services
  services="$(docker compose $DBX_COMPOSE_ARGS config --services)"
  for candidate in "$@"; do
    while IFS= read -r service; do
      [[ "$service" == "$candidate" ]] && { printf '%s\n' "$service"; return 0; }
    done <<< "$services"
  done
  while IFS= read -r service; do
    [[ -n "$service" ]] || continue
    if dbx_has_command "$service" psql || dbx_has_command "$service" mariadb || dbx_has_command "$service" mysql; then
      printf '%s\n' "$service"
      return 0
    fi
  done <<< "$services"
  return 1
}

dbx_detect_service() {
  dbx_var DB_EXCEL_SERVICE DB_EXPORT_SERVICE DB_IMPORT_SERVICE DB_SERVICE && return 0
  dbx_first_existing_service db postgres database mariadb mysql || die "Could not detect a database service. Set DB_EXCEL_SERVICE in /etc/sgdev-infra/apps/$APP_SLUG.env"
}

dbx_detect_engine() {
  local service="$1"
  local configured
  configured="$(dbx_var DB_EXCEL_ENGINE DB_EXPORT_ENGINE DB_IMPORT_ENGINE DB_ENGINE 2>/dev/null || true)"
  if [[ -n "$configured" ]]; then
    case "$configured" in
      postgres|postgresql) printf '%s\n' "postgres"; return 0 ;;
      mysql|mariadb) printf '%s\n' "mysql"; return 0 ;;
      *) die "Unsupported DB_EXCEL_ENGINE: $configured" ;;
    esac
  fi
  if dbx_has_command "$service" psql; then
    printf '%s\n' "postgres"
    return 0
  fi
  if dbx_has_command "$service" mariadb || dbx_has_command "$service" mysql; then
    printf '%s\n' "mysql"
    return 0
  fi
  die "Could not detect database engine in service $service. Set DB_EXCEL_ENGINE=postgres or mysql"
}

dbx_detect_postgres_user() {
  local service="$1"
  local value
  value="$(dbx_var DB_EXCEL_USER DB_EXPORT_USER DB_IMPORT_USER DB_USER 2>/dev/null || true)"
  [[ -n "$value" ]] && { printf '%s\n' "$value"; return 0; }
  value="$(dbx_container_env "$service" POSTGRES_USER)"
  printf '%s\n' "${value:-postgres}"
}

dbx_detect_postgres_database() {
  local service="$1"
  local user="$2"
  local value
  value="$(dbx_var DB_EXCEL_DATABASE DB_EXPORT_DATABASE DB_IMPORT_DATABASE DB_DATABASE 2>/dev/null || true)"
  [[ -n "$value" ]] && { printf '%s\n' "$value"; return 0; }
  value="$(dbx_container_env "$service" POSTGRES_DB)"
  printf '%s\n' "${value:-$user}"
}

dbx_detect_mysql_user() {
  local service="$1"
  local value
  value="$(dbx_var DB_EXCEL_USER DB_EXPORT_USER DB_IMPORT_USER DB_USER 2>/dev/null || true)"
  [[ -n "$value" ]] && { printf '%s\n' "$value"; return 0; }
  value="$(dbx_container_env "$service" MYSQL_USER)"
  [[ -n "$value" ]] || value="$(dbx_container_env "$service" MARIADB_USER)"
  printf '%s\n' "${value:-root}"
}

dbx_detect_mysql_database() {
  local service="$1"
  local value
  value="$(dbx_var DB_EXCEL_DATABASE DB_EXPORT_DATABASE DB_IMPORT_DATABASE DB_DATABASE 2>/dev/null || true)"
  [[ -n "$value" ]] && { printf '%s\n' "$value"; return 0; }
  value="$(dbx_container_env "$service" MYSQL_DATABASE)"
  [[ -n "$value" ]] || value="$(dbx_container_env "$service" MARIADB_DATABASE)"
  [[ -n "$value" ]] || value="$(dbx_container_env "$service" WORDPRESS_DB_NAME)"
  [[ -n "$value" ]] || die "Could not detect MySQL/MariaDB database. Set DB_EXCEL_DATABASE"
  printf '%s\n' "$value"
}

dbx_pg_exec() {
  local service="$1"
  local user="$2"
  local database="$3"
  local password
  password="$(dbx_var DB_EXCEL_PASSWORD DB_EXPORT_PASSWORD DB_IMPORT_PASSWORD DB_PASSWORD 2>/dev/null || true)"
  # shellcheck disable=SC2086
  docker compose $DBX_COMPOSE_ARGS exec -T -e "DB_EXCEL_PASSWORD=$password" "$service" sh -lc '
    user="$1"
    database="$2"
    export PGPASSWORD="${DB_EXCEL_PASSWORD:-${POSTGRES_PASSWORD:-${PGPASSWORD:-}}}"
    exec psql -v ON_ERROR_STOP=1 -X -qAt -U "$user" -d "$database"
  ' sh "$user" "$database"
}

dbx_mysql_exec() {
  local service="$1"
  local user="$2"
  local database="$3"
  local password
  password="$(dbx_var DB_EXCEL_PASSWORD DB_EXPORT_PASSWORD DB_IMPORT_PASSWORD DB_PASSWORD 2>/dev/null || true)"
  # shellcheck disable=SC2086
  docker compose $DBX_COMPOSE_ARGS exec -T -e "DB_EXCEL_PASSWORD=$password" "$service" sh -lc '
    user="$1"
    database="$2"
    if command -v mariadb >/dev/null 2>&1; then
      client="mariadb"
    else
      client="mysql"
    fi
    password="${DB_EXCEL_PASSWORD:-${MYSQL_PASSWORD:-${MARIADB_PASSWORD:-${MYSQL_ROOT_PASSWORD:-${MARIADB_ROOT_PASSWORD:-}}}}}"
    MYSQL_PWD="$password" exec "$client" --batch --raw --skip-column-names --default-character-set=utf8mb4 -u "$user" "$database"
  ' sh "$user" "$database"
}
