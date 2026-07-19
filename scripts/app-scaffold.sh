#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

[[ $# -eq 3 ]] || die "Usage: ./scripts/app-scaffold.sh <slug> <repo-dir> <vite-static|spring-boot>"

slug="$1"
repo_dir="$2"
preset="$3"
app_root="$(realpath -m "$SGDEV_APPS_ROOT/$slug")"
generated_dir="$app_root/generated"

ensure_slug "$slug"
[[ "$(realpath -m "$repo_dir")" == "$app_root"/* ]] || die "repo-dir must stay inside $app_root"
[[ -d "$repo_dir" ]] || die "Repository directory does not exist: $repo_dir"

mkdir -p "$generated_dir"

write_vite_static() {
  [[ -f "$repo_dir/package.json" ]] || die "vite-static requires package.json in $repo_dir"
  [[ -f "$repo_dir/package-lock.json" ]] || die "vite-static currently requires package-lock.json"

  cat > "$generated_dir/Dockerfile" <<'DOCKERFILE'
FROM node:22-alpine AS build
WORKDIR /workspace
COPY repo/package.json repo/package-lock.json ./
RUN npm ci
COPY repo/ ./
RUN npm run build -- --base=./

FROM nginx:1.27-alpine
COPY --from=build /workspace/dist/ /usr/share/nginx/html/
RUN printf '%s\n' \
  'server {' \
  '  listen 80;' \
  '  server_name _;' \
  '  root /usr/share/nginx/html;' \
  '  location / {' \
  '    try_files $uri $uri/ /index.html;' \
  '  }' \
  '}' > /etc/nginx/conf.d/default.conf
EXPOSE 80
DOCKERFILE

  cat > "$generated_dir/compose.yml" <<COMPOSE
name: sgdev-$slug
services:
  web:
    build:
      context: ..
      dockerfile: generated/Dockerfile
    restart: unless-stopped
    expose:
      - "80"
    networks:
      proxy:
        aliases:
          - $slug-web

networks:
  proxy:
    external: true
    name: \${PROXY_NETWORK:-sgdev-proxy}
COMPOSE
}

write_spring_boot() {
  if [[ ! -f "$repo_dir/mvnw" && ! -f "$repo_dir/gradlew" ]]; then
    die "spring-boot requires mvnw or gradlew in $repo_dir"
  fi

  cat > "$generated_dir/Dockerfile" <<'DOCKERFILE'
FROM eclipse-temurin:21-jdk-alpine AS build
WORKDIR /workspace
COPY repo/ ./
RUN set -eux; \
    if [ -f ./mvnw ]; then chmod +x ./mvnw && ./mvnw -DskipTests package; \
    else chmod +x ./gradlew && ./gradlew bootJar -x test; fi; \
    artifact="$(find target build/libs -type f -name '*.jar' ! -name '*-plain.jar' ! -name '*-sources.jar' | head -n 1)"; \
    test -n "$artifact"; \
    cp "$artifact" /tmp/app.jar

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=build /tmp/app.jar /app/app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
DOCKERFILE

  cat > "$generated_dir/compose.yml" <<COMPOSE
name: sgdev-$slug
services:
  web:
    build:
      context: ..
      dockerfile: generated/Dockerfile
    restart: unless-stopped
    expose:
      - "8080"
    networks:
      proxy:
        aliases:
          - $slug-web

networks:
  proxy:
    external: true
    name: \${PROXY_NETWORK:-sgdev-proxy}
COMPOSE
}

case "$preset" in
  vite-static)
    write_vite_static
    ;;
  spring-boot)
    write_spring_boot
    ;;
  *)
    die "Unsupported scaffold preset: $preset"
    ;;
esac

chmod 0644 "$generated_dir/Dockerfile" "$generated_dir/compose.yml"
log "Generated $preset Docker files in $generated_dir"
