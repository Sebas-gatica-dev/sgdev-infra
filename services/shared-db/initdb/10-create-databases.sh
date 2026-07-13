#!/usr/bin/env bash
set -euo pipefail

ensure_identifier() {
  local value="$1"
  [[ "$value" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || {
    echo "Invalid PostgreSQL identifier: $value" >&2
    exit 1
  }
}

sql_escape() {
  local value="$1"
  value="${value//\'/\'\'}"
  printf '%s' "$value"
}

create_role_if_missing() {
  local role="$1"
  local password="$2"
  local password_sql
  ensure_identifier "$role"
  password_sql="$(sql_escape "$password")"

  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$role') THEN
    CREATE ROLE "$role" LOGIN PASSWORD '$password_sql';
  ELSE
    ALTER ROLE "$role" WITH LOGIN PASSWORD '$password_sql';
  END IF;
END
\$\$;
SQL
}

create_database_if_missing() {
  local database="$1"
  local owner="$2"
  ensure_identifier "$database"
  ensure_identifier "$owner"

  if ! psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_database WHERE datname = '$database'" | grep -q 1; then
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "CREATE DATABASE \"$database\" OWNER \"$owner\";"
  fi
}

enable_extensions() {
  local database="$1"
  local owner="$2"
  ensure_identifier "$database"
  ensure_identifier "$owner"

  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$database" <<SQL
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
GRANT CONNECT ON DATABASE "$database" TO "$owner";
GRANT USAGE, CREATE ON SCHEMA public TO "$owner";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "$owner";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO "$owner";
SQL
}

create_role_if_missing "$ARGENTICOMMERCE_DB_USER" "$ARGENTICOMMERCE_DB_PASSWORD"
create_database_if_missing "$ARGENTICOMMERCE_DB" "$ARGENTICOMMERCE_DB_USER"
enable_extensions "$ARGENTICOMMERCE_DB" "$ARGENTICOMMERCE_DB_USER"

create_role_if_missing "$MERCADOLIBRE_DB_USER" "$MERCADOLIBRE_DB_PASSWORD"
create_database_if_missing "$MERCADOLIBRE_DB" "$MERCADOLIBRE_DB_USER"
enable_extensions "$MERCADOLIBRE_DB" "$MERCADOLIBRE_DB_USER"

create_role_if_missing "$RAG_DB_USER" "$RAG_DB_PASSWORD"
create_database_if_missing "$RAG_DB" "$RAG_DB_USER"
enable_extensions "$RAG_DB" "$RAG_DB_USER"
