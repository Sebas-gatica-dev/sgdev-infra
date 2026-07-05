#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

usage() {
  cat <<'USAGE'
Usage:
  sudo bash ./scripts/app-new-wordpress.sh <slug> <domain> [app-path] [content-repo-url] [content-branch]

Example:
  sudo env WORDPRESS_SITE_TITLE="Blog SGDEV" \
    WORDPRESS_ADMIN_EMAIL="admin@sgdev.com.ar" \
    bash ./scripts/app-new-wordpress.sh blog sgdev.com.ar /blog https://github.com/owner/wp-content.git main

Creates:
  - /opt/apps/<slug>/repo/compose.yml
  - /opt/apps/<slug>/repo/.env
  - /opt/apps/<slug>/repo/wp-content
  - /etc/sgdev-infra/apps/<slug>.env

Then deploy with:
  ./scripts/app-deploy.sh <slug> --no-pull
USAGE
}

[[ $# -ge 2 ]] || { usage; exit 1; }

slug="$1"
domain="$2"
app_path="${3:-/}"
content_repo="${4:-}"
content_branch="${5:-main}"

ensure_slug "$slug"
[[ -n "$domain" ]] || die "Domain is required"
[[ "$app_path" == /* ]] || die "app-path must start with /"
[[ "$app_path" != "/" ]] || die "app-path cannot be / with the current shared path router; use /blog or add host-specific Nginx routing"

app_id="${APP_ID:-app_${slug//-/_}}"
repo_dir="${SGDEV_APPS_ROOT}/${slug}/repo"
wp_content_dir="$repo_dir/wp-content"
config_file="$SGDEV_APPS_CONFIG_DIR/$slug.env"
public_path="$app_path"
if [[ "$public_path" == "/" ]]; then
  public_url="https://$domain"
else
  public_url="https://$domain${public_path%/}"
fi

make_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 32 | tr -d '\n'
  else
    printf '%s_%s_change_me' "$slug" "$(date +%s)"
  fi
}

db_name="${WORDPRESS_DB_NAME:-wp_${slug//-/_}}"
db_user="${WORDPRESS_DB_USER:-wp_${slug//-/_}}"
db_password="${WORDPRESS_DB_PASSWORD:-$(make_secret)}"
mysql_root_password="${MYSQL_ROOT_PASSWORD:-$(make_secret)}"
table_prefix="${WORDPRESS_TABLE_PREFIX:-wp_}"
site_title="${WORDPRESS_SITE_TITLE:-$slug}"
admin_email="${WORDPRESS_ADMIN_EMAIL:-admin@$domain}"

mkdir -p "$SGDEV_APPS_CONFIG_DIR" "$repo_dir" "$wp_content_dir" "$SGDEV_BACKUPS_ROOT/$slug"
[[ ! -e "$config_file" ]] || die "Config already exists: $config_file"
[[ ! -e "$repo_dir/compose.yml" ]] || die "Compose already exists: $repo_dir/compose.yml"

cat > "$repo_dir/compose.yml" <<EOF
name: $slug

services:
  wordpress:
    image: wordpress:6.6-php8.3-apache
    container_name: $slug-wordpress
    restart: unless-stopped
    depends_on:
      - db
    environment:
      WORDPRESS_DB_HOST: db:3306
      WORDPRESS_DB_NAME: \${WORDPRESS_DB_NAME}
      WORDPRESS_DB_USER: \${WORDPRESS_DB_USER}
      WORDPRESS_DB_PASSWORD: \${WORDPRESS_DB_PASSWORD}
      WORDPRESS_TABLE_PREFIX: \${WORDPRESS_TABLE_PREFIX:-wp_}
      WORDPRESS_CONFIG_EXTRA: |
        define('WP_HOME', getenv('WORDPRESS_HOME'));
        define('WP_SITEURL', getenv('WORDPRESS_SITEURL'));
        define('FORCE_SSL_ADMIN', true);
        if (isset(\$_SERVER['HTTP_X_FORWARDED_PROTO']) && \$_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https') {
            \$_SERVER['HTTPS'] = 'on';
        }
    volumes:
      - wordpress_data:/var/www/html
      - ./wp-content:/var/www/html/wp-content
    expose:
      - "80"
    networks:
      proxy:
        aliases:
          - $slug-wordpress
      internal:

  db:
    image: mariadb:11.4
    container_name: $slug-db
    restart: unless-stopped
    environment:
      MYSQL_DATABASE: \${WORDPRESS_DB_NAME}
      MYSQL_USER: \${WORDPRESS_DB_USER}
      MYSQL_PASSWORD: \${WORDPRESS_DB_PASSWORD}
      MYSQL_ROOT_PASSWORD: \${MYSQL_ROOT_PASSWORD}
    volumes:
      - mariadb_data:/var/lib/mysql
    networks:
      - internal

volumes:
  wordpress_data:
  mariadb_data:

networks:
  proxy:
    external: true
    name: $PROXY_NETWORK
  internal:
    internal: true
EOF

cat > "$repo_dir/.env" <<EOF
WORDPRESS_DB_NAME=$db_name
WORDPRESS_DB_USER=$db_user
WORDPRESS_DB_PASSWORD=$db_password
MYSQL_ROOT_PASSWORD=$mysql_root_password
WORDPRESS_TABLE_PREFIX=$table_prefix
WORDPRESS_HOME=$public_url
WORDPRESS_SITEURL=$public_url
WORDPRESS_SITE_TITLE=$site_title
WORDPRESS_ADMIN_EMAIL=$admin_email
EOF

cat > "$repo_dir/.gitignore" <<'EOF'
.env
wp-content/uploads/
EOF

if [[ -n "$content_repo" ]]; then
  require_command git
  tmp_dir="$(mktemp -d)"
  log "Cloning WordPress content repo $content_repo"
  git clone --depth 1 --branch "$content_branch" "$content_repo" "$tmp_dir"
  if [[ -d "$tmp_dir/wp-content" ]]; then
    cp -a "$tmp_dir/wp-content/." "$wp_content_dir/"
  else
    cp -a "$tmp_dir/." "$wp_content_dir/"
  fi
  rm -rf "$tmp_dir"
fi

if [[ ! -d "$repo_dir/.git" ]]; then
  git -C "$repo_dir" init --initial-branch=main >/dev/null
fi

cat > "$config_file" <<EOF
APP_SLUG=$slug
APP_ID=$app_id
APP_DOMAIN=$domain
APP_PATH=$app_path
APP_UPSTREAM=http://$slug-wordpress:80
APP_ROOT=$SGDEV_APPS_ROOT/$slug
REPO_DIR=$repo_dir
COMPOSE_FILES="compose.yml"
ENV_FILE=.env
BRANCH=main
STRIP_PREFIX=true
CLIENT_MAX_BODY_SIZE=64m
PROXY_CONNECT_TIMEOUT=10s
PROXY_READ_TIMEOUT=180s
PROXY_SEND_TIMEOUT=180s
BACKUP_DIR=$SGDEV_BACKUPS_ROOT/$slug
BACKUP_VOLUMES="${slug}_wordpress_data ${slug}_mariadb_data"
WORDPRESS_CONTENT_REPO=$content_repo
DB_EXCEL_ENGINE=mysql
DB_EXCEL_SERVICE=db
DB_EXCEL_DATABASE=$db_name
DB_EXCEL_USER=$db_user
EOF

"$SCRIPT_DIR/app-render-nginx.sh" "$slug"

log "Created WordPress app scaffold: $repo_dir"
log "Review $repo_dir/.env, then run: ./scripts/app-deploy.sh $slug --no-pull"
