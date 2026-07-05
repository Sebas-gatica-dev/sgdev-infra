(function () {
  "use strict";

  var BASE = "/admin";
  var STORE_KEY = "sgdev.admin.state.v1";
  var SESSION_KEY = "sgdev.admin.session.v1";
  var API_TOKEN_KEY = "sgdev.admin.api.token.v1";
  var MONITOR_REFRESH_MS = 10000;
  var app = document.getElementById("app");
  var remote = {
    available: false,
    loading: false,
    error: "",
    lastSync: "",
    lastAttempt: 0,
    info: null
  };
  var logState = {
    key: "",
    loading: false,
    text: "",
    error: ""
  };
  var actionState = {
    running: false,
    action: "",
    slug: "",
    status: "",
    message: "",
    updatedAt: ""
  };

  var icons = {
    dashboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 13h8V3H3v10zM13 21h8v-8h-8v8zM13 3v8h8V3h-8zM3 21h8v-6H3v6z"/></svg>',
    server: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="6" rx="2"/><rect x="3" y="14" width="18" height="6" rx="2"/><path d="M7 7h.01M7 17h.01"/></svg>',
    plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>',
    logs: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 6h16M4 12h16M4 18h10"/></svg>',
    chart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19V5M4 19h16"/><path d="M8 15l3-4 3 2 4-7"/></svg>',
    database: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>',
    domain: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.2 2.5 3.3 5.5 3.3 9s-1.1 6.5-3.3 9M12 3C9.8 5.5 8.7 8.5 8.7 12s1.1 6.5 3.3 9"/></svg>',
    cicd: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 7h10v10H7z"/><path d="M4 12H2M22 12h-2M12 4V2M12 22v-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M18.4 5.6l1.4-1.4M4.2 19.8l1.4-1.4"/></svg>',
    help: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9.1 9a3 3 0 1 1 5.2 2c-.9.8-1.8 1.3-2 2.8"/><path d="M12 17h.01"/></svg>',
    play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>',
    stop: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 7h10v10H7z"/></svg>',
    trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2M6 6l1 15h10l1-15"/></svg>',
    copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3 4 6v6c0 5 3.4 8.3 8 9 4.6-.7 8-4 8-9V6l-8-3z"/><path d="m9 12 2 2 4-5"/></svg>',
    bolt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/></svg>',
    backup: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v10"/><path d="m8 9 4 4 4-4"/><path d="M5 17v2h14v-2"/></svg>',
    upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21V11"/><path d="m8 15 4-4 4 4"/><path d="M5 7V5h14v2"/></svg>',
    refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6v5h-5"/><path d="M4 18v-5h5"/><path d="M19 11a7 7 0 0 0-12.1-4.8M5 13a7 7 0 0 0 12.1 4.8"/></svg>',
    external: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 3h7v7"/><path d="M10 14 21 3"/><path d="M21 14v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h6"/></svg>',
    lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
    wordpress: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="currentColor"/><text x="12" y="15.4" text-anchor="middle" fill="white" font-size="10.4" font-family="Georgia, serif" font-weight="700">W</text></svg>'
  };

  var navItems = [
    ["dashboard", "Tablero", icons.dashboard],
    ["apps", "Apps", icons.server],
    ["logs", "Logs", icons.logs],
    ["metrics", "Monitoreo", icons.chart],
    ["database", "Base de datos", icons.database],
    ["domains", "Dominios", icons.domain],
    ["cicd", "CI/CD", icons.cicd],
    ["help", "Ayuda", icons.help]
  ];

  var helpTemplates = {
    checklist: {
      title: "Checklist de alta",
      body: [
        "1. Elegir slug estable: miapp, janoai, portfolio.",
        "2. Confirmar repo GitHub, branch, compose y .env.",
        "3. Definir APP_PATH si comparte dominio: /miapp.",
        "4. Definir dominio dedicado si corresponde: miapp.com.ar.",
        "5. Confirmar APP_UPSTREAM: http://miapp-web:80.",
        "6. Verificar que el servicio web use la red externa sgdev-proxy.",
        "7. Crear /etc/sgdev-infra/apps/miapp.env.",
        "8. Ejecutar ./scripts/app-deploy.sh miapp.",
        "9. Probar /health, ruta publica y logs.",
        "10. Configurar backup si hay datos persistentes."
      ].join("\\n")
    },
    operations: {
      title: "Comandos diarios",
      body: [
        "# Estado general",
        "./scripts/app-status.sh",
        "",
        "# Estado de una app",
        "./scripts/app-status.sh portfolio",
        "",
        "# Logs",
        "./scripts/app-logs.sh portfolio",
        "",
        "# Deploy con pull/build/reload",
        "./scripts/app-deploy.sh portfolio",
        "",
        "# Deploy sin pull",
        "./scripts/app-deploy.sh portfolio --no-pull",
        "",
        "# Detener sin borrar volumenes",
        "./scripts/app-stop.sh portfolio",
        "",
        "# Sacar del proxy sin borrar datos",
        "./scripts/app-remove.sh portfolio",
        "",
        "# Backup",
        "./scripts/app-backup.sh portfolio"
      ].join("\\n")
    },
    deployStepByStep: {
      title: "Deploy paso a paso",
      body: [
        "Flujo desde el admin:",
        "",
        "1. Entrar a /admin con el usuario local.",
        "2. Confirmar que el boton superior diga VPS real.",
        "3. Ir a Tablero o Apps.",
        "4. Elegir la app.",
        "5. Presionar Deploy.",
        "6. Esperar el banner Accion completada.",
        "7. Abrir Logs desde el banner o desde la app.",
        "8. Validar la URL publica.",
        "",
        "Flujo manual equivalente por SSH:",
        "",
        "cd /opt/sgdev-infra",
        "./scripts/app-status.sh portfolio",
        "./scripts/app-deploy.sh portfolio",
        "./scripts/app-logs.sh portfolio",
        "curl -I https://sgdev.com.ar/portfolio/",
        "",
        "Deploy sin git pull:",
        "",
        "./scripts/app-deploy.sh portfolio --no-pull",
        "",
        "Si falla:",
        "",
        "./scripts/app-status.sh portfolio",
        "./scripts/app-logs.sh portfolio",
        "docker ps",
        "docker compose -f /opt/sgdev-infra/proxy/compose.yml logs --tail 100 nginx"
      ].join("\\n")
    },
    env: {
      title: "Plantilla /etc/sgdev-infra/apps/<slug>.env",
      body: [
        "APP_SLUG=miapp",
        "APP_ID=app_miapp",
        "APP_DOMAIN=sgdev.com.ar",
        "APP_PATH=/miapp",
        "APP_UPSTREAM=http://miapp-web:80",
        "APP_ROOT=/opt/apps/miapp",
        "REPO_DIR=/opt/apps/miapp/repo",
        "GIT_REMOTE_URL=https://github.com/owner/miapp.git",
        "BRANCH=main",
        "COMPOSE_FILES=\"compose.yml\"",
        "ENV_FILE=.env",
        "STRIP_PREFIX=true",
        "CLIENT_MAX_BODY_SIZE=25m",
        "PROXY_CONNECT_TIMEOUT=10s",
        "PROXY_READ_TIMEOUT=120s",
        "PROXY_SEND_TIMEOUT=120s",
        "BACKUP_DIR=/opt/backups/miapp",
        "BACKUP_VOLUMES=\"miapp_postgres_data\"",
        "",
        "# Export/import Excel de base de datos",
        "DB_EXCEL_ENGINE=postgres",
        "DB_EXCEL_SERVICE=db",
        "DB_EXCEL_DATABASE=app",
        "DB_EXCEL_USER=app",
        "DB_EXCEL_APP_ID_COLUMN=app_id"
      ].join("\\n")
    },
    compose: {
      title: "compose.yml minimo",
      body: [
        "name: miapp",
        "",
        "services:",
        "  web:",
        "    build:",
        "      context: .",
        "      dockerfile: Dockerfile",
        "    container_name: miapp-web",
        "    restart: unless-stopped",
        "    env_file:",
        "      - .env",
        "    expose:",
        "      - \"80\"",
        "    networks:",
        "      proxy:",
        "        aliases:",
        "          - miapp-web",
        "      internal:",
        "",
        "  db:",
        "    image: postgres:16-alpine",
        "    restart: unless-stopped",
        "    environment:",
        "      POSTGRES_DB: ${POSTGRES_DB:-app}",
        "      POSTGRES_USER: ${POSTGRES_USER:-app}",
        "      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?missing}",
        "    volumes:",
        "      - postgres_data:/var/lib/postgresql/data",
        "    networks:",
        "      - internal",
        "",
        "volumes:",
        "  postgres_data:",
        "    name: miapp_postgres_data",
        "",
        "networks:",
        "  proxy:",
        "    external: true",
        "    name: sgdev-proxy",
        "  internal:",
        "    internal: true"
      ].join("\\n")
    },
    dockerfile: {
      title: "Dockerfile frontend estatico",
      body: [
        "FROM node:22-alpine AS build",
        "WORKDIR /app",
        "COPY package*.json ./",
        "RUN npm ci",
        "COPY . .",
        "ARG PUBLIC_BASE_PATH=/miapp/",
        "ENV VITE_BASE_PATH=$PUBLIC_BASE_PATH",
        "RUN npm run build",
        "",
        "FROM nginx:1.27-alpine",
        "COPY nginx.conf /etc/nginx/conf.d/default.conf",
        "COPY --from=build /app/dist /usr/share/nginx/html",
        "EXPOSE 80"
      ].join("\\n")
    },
    nginx: {
      title: "nginx.conf interno de una app",
      body: [
        "server {",
        "    listen 80;",
        "    server_name _;",
        "    root /usr/share/nginx/html;",
        "    index index.html;",
        "",
        "    location = /health {",
        "        access_log off;",
        "        add_header Content-Type text/plain;",
        "        return 200 \"ok\\n\";",
        "    }",
        "",
        "    location / {",
        "        try_files $uri $uri/ /index.html;",
        "    }",
        "}"
      ].join("\\n")
    },
    db: {
      title: "Modelo app_id compartido",
      body: [
        "create extension if not exists pgcrypto;",
        "",
        "create table if not exists app_registry (",
        "  app_id uuid primary key default gen_random_uuid(),",
        "  slug text not null unique,",
        "  display_name text not null,",
        "  domain text not null,",
        "  base_path text not null default '/',",
        "  repo_url text,",
        "  status text not null default 'active',",
        "  created_at timestamptz not null default now()",
        ");",
        "",
        "alter table portfolio_sections",
        "  add column if not exists app_id uuid references app_registry(app_id);",
        "",
        "create index if not exists portfolio_sections_app_id_idx",
        "  on portfolio_sections(app_id);",
        "",
        "-- Toda query operativa debe filtrar por app_id.",
        "select *",
        "from portfolio_sections",
        "where app_id = (select app_id from app_registry where slug = 'portfolio')",
        "order by sort_order asc;"
      ].join("\\n")
    },
    github: {
      title: "GitHub Actions deploy manual",
      body: [
        "name: Manual deploy",
        "",
        "on:",
        "  workflow_dispatch:",
        "    inputs:",
        "      app:",
        "        description: App slug",
        "        required: true",
        "        default: miapp",
        "",
        "jobs:",
        "  deploy:",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - name: Deploy over SSH",
        "        uses: appleboy/ssh-action@v1.0.3",
        "        with:",
        "          host: ${{ secrets.VPS_HOST }}",
        "          username: ${{ secrets.VPS_USER }}",
        "          key: ${{ secrets.VPS_SSH_KEY }}",
        "          port: ${{ secrets.VPS_PORT }}",
        "          script: |",
        "            cd /opt/sgdev-infra",
        "            git pull --ff-only",
        "            ./scripts/app-deploy.sh ${{ inputs.app }}"
      ].join("\\n")
    },
    wordpress: {
      title: "WordPress Docker minimo",
      body: [
        "# Con el proxy actual usar subruta, por ejemplo /blog.",
        "# Para raiz de dominio dedicado falta sumar server blocks por host.",
        "",
        "Carpetas:",
        "/opt/apps/blog/repo",
        "/opt/apps/blog/repo/wp-content",
        "/opt/backups/blog",
        "",
        "Servicios:",
        "- wordpress:6.6-php8.3-apache",
        "- mariadb:11.4",
        "",
        "Variables minimas:",
        "WORDPRESS_DB_HOST=db:3306",
        "WORDPRESS_DB_NAME=wordpress",
        "WORDPRESS_DB_USER=wordpress",
        "WORDPRESS_DB_PASSWORD=usar_un_password_largo",
        "MYSQL_ROOT_PASSWORD=usar_otro_password_largo",
        "",
        "Deploy:",
        "sudo bash ./scripts/app-new-wordpress.sh blog sgdev.com.ar /blog",
        "./scripts/app-deploy.sh blog --no-pull",
        "",
        "Si ya tenes un repo con Dockerfile/compose propio, usalo como proyecto normal.",
        "La receta de WordPress conviene cuando queres que SGDEV genere los archivos base."
      ].join("\\n")
    },
    adminApi: {
      title: "Admin API local y VPS",
      body: [
        "# En la VPS: instala monitor 9100 y control 9101",
        "cd /opt/sgdev-infra",
        "sudo chmod +x scripts/*.sh",
        "sudo ./scripts/install-admin-api.sh",
        "./scripts/sync-ssl-conf.sh",
        "./scripts/proxy-reload.sh",
        "systemctl status sgdev-admin-control-api.service",
        "",
        "# El admin usa /admin-api/ -> host.docker.internal:9101",
        "# En Linux el servicio suele bindear sobre docker0, por ejemplo 172.17.0.1",
        "curl -i https://sgdev.com.ar/admin-api/health",
        "curl -H \"Authorization: Bearer TOKEN\" https://sgdev.com.ar/admin-api/state",
        "",
        "# En local: puente por SSH hacia la VPS",
        "# .env.admin.local queda fuera de Git",
        "SGDEV_ADMIN_API_HOST=127.0.0.1",
        "SGDEV_ADMIN_API_PORT=9101",
        "SGDEV_ADMIN_API_MODE=ssh",
        "SGDEV_ADMIN_USERNAME=root",
        "SGDEV_ADMIN_PASSWORD=********",
        "SGDEV_VPS_HOST=IP_O_HOST",
        "SGDEV_VPS_PORT=22022",
        "SGDEV_VPS_USER=root",
        "SGDEV_VPS_PASSWORD=********",
        "SGDEV_REMOTE_INFRA_ROOT=/opt/sgdev-infra",
        "",
        "# Arrancar API local de desarrollo",
        "python -m pip install paramiko",
        "python admin_api.py",
        "curl -H \"Authorization: Bearer ********\" http://127.0.0.1:9101/state"
      ].join("\\n")
    },
    terraform: {
      title: "Terraform variables minimas",
      body: [
        "project_id      = \"mi-proyecto-gcp\"",
        "region          = \"southamerica-east1\"",
        "zone            = \"southamerica-east1-a\"",
        "instance_name   = \"sgdev-vps\"",
        "machine_type    = \"e2-small\"",
        "ssh_user        = \"root\"",
        "ssh_public_key  = \"ssh-ed25519 AAAA...\"",
        "domain_names    = [\"sgdev.com.ar\", \"www.sgdev.com.ar\", \"janoai.com.ar\"]",
        "admin_path      = \"/admin\""
      ].join("\\n")
    }
  };

  var helpGroups = [
    { id: "operate", label: "Operación", keys: ["checklist", "deployStepByStep", "operations", "adminApi"] },
    { id: "apps", label: "Apps Docker", keys: ["env", "compose", "dockerfile", "nginx"] },
    { id: "wordpress", label: "WordPress", keys: ["wordpress"] },
    { id: "database", label: "Base de datos", keys: ["db"] },
    { id: "cicd", label: "CI/CD", keys: ["github"] },
    { id: "infra", label: "Infra", keys: ["terraform"] }
  ];

  function defaultState() {
    return {
      settings: {
        controlDomain: "sgdev.com.ar",
        adminPath: "/admin",
        proxyNetwork: "sgdev-proxy",
        appsRoot: "/opt/apps",
        configRoot: "/etc/sgdev-infra/apps",
        backupsRoot: "/opt/backups",
        deployHookPath: "/__deploy/github/"
      },
      ui: {
        activeApp: "portfolio",
        helpSection: "operate",
        helpTemplate: "checklist",
        logService: "all"
      },
      apps: [],
      operations: [],
      remoteHydrated: false
    };
  }

  function loadState() {
    try {
      var saved = JSON.parse(localStorage.getItem(STORE_KEY));
      if (!saved || !Array.isArray(saved.apps)) return defaultState();
      var base = defaultState();
      saved.settings = Object.assign(base.settings, saved.settings || {});
      saved.ui = Object.assign(base.ui, saved.ui || {});
      if (saved.remoteHydrated !== true) {
        saved.apps = [];
        saved.operations = [];
      } else {
        saved.operations = Array.isArray(saved.operations) ? saved.operations : base.operations;
      }
      saved.remoteHydrated = saved.remoteHydrated === true;
      return saved;
    } catch (error) {
      return defaultState();
    }
  }

  var state = loadState();
  var session = loadSession();
  var monitorState = {
    snapshot: null,
    error: null,
    loading: false,
    lastFetch: 0
  };

  function loadAdminApiToken() {
    try {
      return localStorage.getItem(API_TOKEN_KEY) || "";
    } catch (error) {
      return "";
    }
  }

  function saveAdminApiToken(value) {
    try {
      if (value) localStorage.setItem(API_TOKEN_KEY, value);
      else localStorage.removeItem(API_TOKEN_KEY);
    } catch (error) {
      return;
    }
  }

  function isMonitorRoute(route) {
    return route === "dashboard" || route === "metrics";
  }

  function requestMonitorSnapshot(force) {
    if (!session || !isMonitorRoute(currentRoute()) || !window.fetch) return;
    var now = Date.now();
    if (!force && remote.loading) return;
    if (!force && remote.available && now - monitorState.lastFetch < MONITOR_REFRESH_MS) return;
    monitorState.lastFetch = now;
    syncRemoteState(!force);
  }

  function loadSession() {
    try {
      return JSON.parse(localStorage.getItem(SESSION_KEY));
    } catch (error) {
      return null;
    }
  }

  function saveState() {
    localStorage.setItem(STORE_KEY, JSON.stringify(state));
  }

  function saveSession(value) {
    session = value;
    if (value) localStorage.setItem(SESSION_KEY, JSON.stringify(value));
    else localStorage.removeItem(SESSION_KEY);
  }

  function authHeaders(extra) {
    var headers = Object.assign({}, extra || {});
    var token = (session && session.token) || loadAdminApiToken();
    if (token) {
      headers.Authorization = "Bearer " + token;
      headers["X-Sgdev-Admin-Token"] = token;
    }
    return headers;
  }

  async function apiRequest(path, options) {
    var response = await fetch("/admin-api" + path, Object.assign({
      headers: authHeaders({ "Accept": "application/json" })
    }, options || {}));
    var payload = await response.json().catch(function () { return {}; });
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || ("HTTP " + response.status));
    }
    return payload;
  }

  function payloadToMonitorSnapshot(payload) {
    if (payload.snapshot) return payload.snapshot;
    var info = payload.remote || {};
    var apps = Array.isArray(payload.apps) ? payload.apps : [];
    var load = String(info.loadAvg || "0 0 0").split(/\s+/).slice(0, 3);
    var memoryMatch = String(info.memory || "").match(/(\d+)\/(\d+)MB\s+(\d+)%/);
    var usedMb = memoryMatch ? Number(memoryMatch[1]) : 0;
    var totalMb = memoryMatch ? Number(memoryMatch[2]) : 0;
    var memoryPercent = memoryMatch ? Number(memoryMatch[3]) : Math.round(avg("memory"));
    var diskPercent = Number(String(info.diskRoot || "0").replace("%", "")) || Math.round(avg("disk"));
    var containers = [];
    apps.forEach(function (item) {
      (item.containers || []).forEach(function (name) {
        containers.push({
          name: name,
          image: item.kind === "wordpress" ? "wordpress/mariadb" : "-",
          state: item.status === "running" ? "running" : item.status,
          cpu_percent: Number(item.cpu || 0),
          memory_percent: Number(item.memory || 0),
          memory_usage: "-",
          restart_count: item.restarts || 0,
          compose_project: item.slug
        });
      });
    });
    return {
      generated_at: info.generatedAt || nowStamp(),
      host: {
        hostname: info.hostname || "VPS",
        os: "Linux",
        kernel: "-",
        architecture: "-",
        uptime_seconds: 0
      },
      cpu: {
        cores: "-",
        usage_percent: apps.length ? apps.reduce(function (sum, item) { return sum + Number(item.cpu || 0); }, 0) : 0,
        load_average: load.length ? load : ["0", "0", "0"]
      },
      memory: {
        used_percent: memoryPercent,
        used_bytes: usedMb * 1024 * 1024,
        available_bytes: Math.max(totalMb - usedMb, 0) * 1024 * 1024,
        swap_used_percent: 0,
        swap_used_bytes: 0,
        swap_total_bytes: 0
      },
      disks: [{
        path: "/",
        used_percent: diskPercent,
        used_bytes: 0,
        available_bytes: 0
      }],
      docker: {
        available: true,
        running: apps.filter(function (item) { return item.status === "running"; }).length,
        total: apps.length,
        containers: containers
      },
      processes: {
        count: 0,
        top: [],
        error: ""
      },
      network: {
        interfaces: []
      },
      security: {
        process_args_included: false
      }
    };
  }

  async function syncRemoteState(silent) {
    remote.loading = true;
    remote.lastAttempt = Date.now();
    monitorState.loading = true;
    remote.error = "";
    if (!silent) render();
    try {
      var payload = await apiRequest("/state");
      if (payload.settings) state.settings = Object.assign(state.settings, payload.settings);
      if (Array.isArray(payload.apps)) state.apps = payload.apps;
      if (Array.isArray(payload.operations)) state.operations = payload.operations;
      if (!state.apps.find(function (item) { return item.slug === state.ui.activeApp; })) {
        state.ui.activeApp = state.apps[0] ? state.apps[0].slug : "";
      }
      remote.available = true;
      remote.info = payload.remote || null;
      remote.lastSync = nowStamp();
      state.remoteHydrated = true;
      monitorState.snapshot = payloadToMonitorSnapshot(payload);
      monitorState.error = null;
      saveState();
      if (!silent) toast("Datos reales cargados desde la VPS");
    } catch (error) {
      remote.available = false;
      remote.error = error.message || String(error);
      monitorState.error = remote.error;
      if (!silent) toast("No pude leer la VPS: " + remote.error);
    } finally {
      remote.loading = false;
      monitorState.loading = false;
      render();
    }
  }

  async function runRemoteAction(action, item) {
    actionState = {
      running: true,
      action: action,
      slug: item.slug,
      status: "running",
      message: "Ejecutando en la VPS...",
      updatedAt: nowStamp()
    };
    render();
    try {
      var payload = await apiRequest("/actions", {
        method: "POST",
        headers: authHeaders({
          "Accept": "application/json",
          "Content-Type": "application/json"
        }),
        body: JSON.stringify({
          action: action,
          slug: item.slug,
          noPull: item.kind === "wordpress" && action === "deploy"
        })
      });
      var ok = payload.ok !== false && payload.exitCode === 0;
      actionState = {
        running: false,
        action: action,
        slug: item.slug,
        status: ok ? "ok" : "warn",
        message: ok ? "Accion ejecutada en la VPS." : "La accion termino con error.",
        updatedAt: nowStamp()
      };
      toast(ok ? "Accion real ejecutada en VPS" : "La accion termino con error");
      state.operations.unshift({
        app: item.slug,
        action: action,
        status: ok ? "ok" : "warn",
        at: nowStamp(),
        command: payload.command || shellCommandFor(action, item)
      });
      state.operations = state.operations.slice(0, 12);
      saveState();
      await syncRemoteState(true);
    } catch (error) {
      actionState = {
        running: false,
        action: action,
        slug: item.slug,
        status: "error",
        message: error.message || String(error),
        updatedAt: nowStamp()
      };
      render();
      throw error;
    }
  }

  async function loadRemoteLogs(item) {
    if (!remote.available || !item) return;
    var service = state.ui.logService === "all" ? "" : (state.ui.logService || "");
    var key = item.slug + ":" + service;
    if (logState.loading || logState.key === key && logState.text) return;
    logState = { key: key, loading: true, text: "", error: "" };
    render();
    try {
      var payload = await apiRequest("/logs?slug=" + encodeURIComponent(item.slug) + "&service=" + encodeURIComponent(service) + "&tail=200");
      logState = {
        key: key,
        loading: false,
        text: [payload.stdout || "", payload.stderr || ""].filter(Boolean).join("\n").trim(),
        error: payload.exitCode === 0 ? "" : "docker logs termino con codigo " + payload.exitCode
      };
    } catch (error) {
      logState = { key: key, loading: false, text: "", error: error.message || String(error) };
    }
    render();
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function nowStamp() {
    var date = new Date();
    var pad = function (value) { return String(value).padStart(2, "0"); };
    return [
      date.getFullYear(),
      "-",
      pad(date.getMonth() + 1),
      "-",
      pad(date.getDate()),
      " ",
      pad(date.getHours()),
      ":",
      pad(date.getMinutes())
    ].join("");
  }

  function currentRoute() {
    var path = window.location.pathname;
    if (path === BASE || path === BASE + "/") {
      window.history.replaceState(null, "", BASE + "/login/");
      return "login";
    }
    if (path.indexOf(BASE + "/") !== 0) return "login";
    var route = path.slice(BASE.length).replace(/^\/+|\/+$/g, "").split("/")[0];
    return route || "login";
  }

  function navigate(route) {
    window.history.pushState(null, "", BASE + "/" + route + "/");
    render();
  }

  function appBySlug(slug) {
    return state.apps.find(function (item) { return item.slug === slug; }) || state.apps[0];
  }

  function activeApp() {
    return appBySlug(state.ui.activeApp);
  }

  function publicUrl(item) {
    var path = item.path || "/";
    if (path !== "/" && path.slice(-1) !== "/") path += "/";
    return "https://" + item.domain + path;
  }

  function statusLabel(value) {
    if (value === "running") return "Activo";
    if (value === "idle") return "En pausa";
    return "Detenido";
  }

  function asNumber(value) {
    var number = Number(value);
    return Number.isFinite(number) ? number : 0;
  }

  function formatPercent(value) {
    return asNumber(value).toFixed(asNumber(value) % 1 === 0 ? 0 : 1) + "%";
  }

  function clampPercent(value) {
    return Math.max(0, Math.min(100, asNumber(value)));
  }

  function formatBytes(value) {
    var bytes = asNumber(value);
    var units = ["B", "KB", "MB", "GB", "TB"];
    var index = 0;
    while (bytes >= 1024 && index < units.length - 1) {
      bytes /= 1024;
      index += 1;
    }
    return bytes.toFixed(index === 0 || bytes >= 10 ? 0 : 1) + " " + units[index];
  }

  function formatDuration(seconds) {
    var total = Math.max(0, Math.floor(asNumber(seconds)));
    var days = Math.floor(total / 86400);
    var hours = Math.floor((total % 86400) / 3600);
    var minutes = Math.floor((total % 3600) / 60);
    if (days > 0) return days + "d " + hours + "h";
    if (hours > 0) return hours + "h " + minutes + "m";
    return minutes + "m";
  }

  function formatTimestamp(value) {
    if (!value) return "sin lectura";
    var date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  }

  function primaryDisk(snapshot) {
    if (!snapshot || !Array.isArray(snapshot.disks) || !snapshot.disks.length) return null;
    return snapshot.disks.find(function (disk) { return disk.path === "/opt" || disk.path === "/"; }) || snapshot.disks[0];
  }

  function codeCard(title, code) {
    return [
      '<div class="code-card">',
      "<header><strong>" + escapeHtml(title) + '</strong><button class="btn icon-only ghost" type="button" title="Copiar" aria-label="Copiar" data-copy="' + escapeHtml(code) + '">' + icons.copy + "</button></header>",
      "<pre>" + escapeHtml(code) + "</pre>",
      "</div>"
    ].join("");
  }

  function shellCommandFor(action, item) {
    var slug = item.slug;
    if (action === "deploy") return "./scripts/app-deploy.sh " + slug + (item.kind === "wordpress" ? " --no-pull" : "");
    if (action === "deploy-local") return "./scripts/app-deploy.sh " + slug + " --no-pull";
    if (action === "logs") return "./scripts/app-logs.sh " + slug + (state.ui.logService && state.ui.logService !== "all" ? " " + state.ui.logService : "");
    if (action === "status") return "./scripts/app-status.sh " + slug;
    if (action === "backup") return "./scripts/app-backup.sh " + slug;
    if (action === "stop") return "./scripts/app-stop.sh " + slug;
    if (action === "remove") return "./scripts/app-remove.sh " + slug;
    if (action === "remove-stop") return "./scripts/app-remove.sh " + slug + " --stop";
    return "./scripts/app-status.sh " + slug;
  }

  function render() {
    var route = currentRoute();
    if (!session && route !== "login") {
      window.history.replaceState(null, "", BASE + "/login/");
      route = "login";
    }
    if (session && route === "login") {
      app.innerHTML = renderLogin();
      attachLoginAutofocus();
      return;
    }
    app.innerHTML = route === "login" ? renderLogin() : renderShell(route);
    if (route === "login") attachLoginAutofocus();
    if (session && route !== "login" && !remote.available && !remote.loading && Date.now() - remote.lastAttempt > 5000) {
      window.setTimeout(function () { syncRemoteState(true); }, 0);
    }
    if (session && isMonitorRoute(route)) requestMonitorSnapshot(false);
    if (session && route === "logs") loadRemoteLogs(activeApp());
  }

  function renderLogin() {
    return [
      '<main class="login-screen">',
      '<section class="login-visual">',
      '<div class="brand-lockup"><span class="brand-mark">SG</span><span>SGDEV Infra</span></div>',
      '<div class="login-copy"><p class="eyebrow">Consola privada</p><h1>Control central para tus proyectos.</h1><p>Repositorios, dominios, rutas, logs, metricas, CI/CD manual y plantillas listas para operar la VPS sin perder contexto.</p></div>',
      '<div class="login-stats">',
      '<div class="login-stat"><strong>' + state.apps.length + '</strong><span>apps registradas</span></div>',
      '<div class="login-stat"><strong>' + runningApps() + '</strong><span>servicios activos</span></div>',
      '<div class="login-stat"><strong>' + state.settings.adminPath + '</strong><span>ruta admin</span></div>',
      "</div>",
      "</section>",
      '<section class="login-panel">',
      '<form class="login-card" id="loginForm">',
      '<p class="eyebrow">sgdev.com.ar/admin</p>',
      "<h2>Ingresar</h2>",
      "<p>Usa las credenciales locales configuradas para esta VPS.</p>",
      '<div class="form-grid">',
      '<div class="field full"><label for="loginEmail">Usuario</label><input class="input" id="loginEmail" name="email" type="text" autocomplete="username" value="root" required></div>',
      '<div class="field full"><label for="loginToken">Contraseña</label><input class="input" id="loginToken" name="token" type="password" autocomplete="current-password" minlength="8" placeholder="********" required></div>',
      "</div>",
      '<div class="btn-row" style="margin-top:18px"><button class="btn primary" type="submit">' + icons.lock + " Entrar</button></div>",
      "</form>",
      "</section>",
      "</main>"
    ].join("");
  }

  function attachLoginAutofocus() {
    var input = document.getElementById("loginToken");
    if (input) input.focus();
  }

  function renderShell(route) {
    var renderers = {
      dashboard: renderDashboard,
      apps: renderApps,
      logs: renderLogs,
      metrics: renderMetrics,
      database: renderDatabase,
      domains: renderDomains,
      cicd: renderCicd,
      help: renderHelp
    };
    var normalizedRoute = renderers[route] ? route : "dashboard";
    var renderer = renderers[normalizedRoute];
    return [
      '<div class="app-shell">',
      renderSidebar(normalizedRoute),
      '<main class="main">',
      renderTopbar(normalizedRoute),
      renderGlobalActionBanner(),
      renderer(),
      "</main>",
      "</div>"
    ].join("");
  }

  function renderGlobalActionBanner() {
    if (!actionState.action) return "";
    var pillClass = actionState.running ? "idle" : actionState.status === "ok" ? "running" : "stopped";
    var title = actionState.running ? "Accion en curso" : actionState.status === "ok" ? "Accion completada" : "Accion con error";
    return [
      '<section class="panel action-status-banner">',
      '<div class="section-title"><div><h2>' + title + '</h2><p>' + escapeHtml(actionState.slug + " - " + actionState.action + " - " + actionState.message) + '</p></div><div class="btn-row"><span class="status-pill ' + pillClass + '"><span class="dot"></span>' + (actionState.running ? "Ejecutando" : actionState.status) + '</span><button class="btn" type="button" data-open-logs="' + escapeHtml(actionState.slug) + '">' + icons.logs + " Logs</button></div></div>",
      "</section>"
    ].join("");
  }

  function renderSidebar(route) {
    return [
      '<aside class="sidebar">',
      '<div class="brand-lockup"><span class="brand-mark">SG</span><span>SGDEV Admin</span></div>',
      '<nav class="nav">',
      navItems.map(function (item) {
        return '<button class="nav-item ' + (route === item[0] ? "active" : "") + '" type="button" data-route="' + item[0] + '">' + item[2] + "<span>" + item[1] + "</span></button>";
      }).join(""),
      "</nav>",
      '<div class="sidebar-footer">',
      '<div class="mini-status"><strong>Proxy compartido</strong><span>' + state.settings.controlDomain + state.settings.adminPath + '</span><span>Red Docker: ' + state.settings.proxyNetwork + "</span></div>",
      "</div>",
      "</aside>"
    ].join("");
  }

  function renderTopbar(route) {
    var title = {
      dashboard: ["Tablero", "Estado de VPS, apps y acciones frecuentes."],
      apps: ["Apps", "Inventario operativo de proyectos."],
      logs: ["Logs", "Vista de comandos y salida esperada por servicio."],
      metrics: ["Monitoreo", "CPU, memoria, disco, procesos, red y Docker de la VPS."],
      database: ["Base de datos", "Export/import Excel por proyecto."],
      domains: ["Dominios", "Hosts, rutas y subrutas del proxy Nginx."],
      cicd: ["CI/CD", "Deploys manuales, backups y webhooks."],
      help: ["Ayuda", "Recordatorios y plantillas para copiar."]
    }[route] || ["Tablero", "Estado general."];
    var syncText = remote.loading ? "Sincronizando" : remote.available ? "VPS real" : "Conectar VPS";
    var syncClass = remote.available ? "primary" : "";
    return [
      '<header class="topbar">',
      '<div class="view-title"><h1>' + title[0] + "</h1><p>" + title[1] + "</p></div>",
      '<div class="top-actions">',
      '<select class="select mobile-nav" id="mobileNav" aria-label="Navegacion">' + navItems.map(function (item) { return '<option value="' + item[0] + '"' + (route === item[0] ? " selected" : "") + ">" + item[1] + "</option>"; }).join("") + "</select>",
      '<button class="btn ' + syncClass + '" type="button" data-action="sync">' + icons.refresh + " " + syncText + "</button>",
      '<button class="btn" type="button" data-route="help">' + icons.help + " Ayuda</button>",
      '<button class="btn" type="button" data-action="logout">Salir</button>',
      "</div>",
      "</header>"
    ].join("");
  }

  function runningApps() {
    return state.apps.filter(function (item) { return item.status === "running"; }).length;
  }

  function renderDashboard() {
    var snapshot = monitorState.snapshot;
    var disk = primaryDisk(snapshot);
    var cpu = snapshot ? formatPercent(snapshot.cpu.usage_percent) : Math.round(avg("cpu")) + "%";
    var memory = snapshot ? formatPercent(snapshot.memory.used_percent) : Math.round(avg("memory")) + "%";
    var diskValue = disk ? formatPercent(disk.used_percent) : Math.round(avg("disk")) + "%";
    var processes = snapshot ? String(snapshot.processes.count || 0) : runningApps() + "/" + state.apps.length;
    return [
      '<section class="metric-grid">',
      stat("Apps activas", runningApps() + "/" + state.apps.length, "green", icons.server),
      stat("CPU VPS", cpu, "blue", icons.chart),
      stat("RAM usada", memory, "amber", icons.database),
      stat("Disco", diskValue, "green", icons.backup),
      stat("Procesos", processes, "violet", icons.bolt),
      "</section>",
      renderMonitorStatusPanel(),
      '<section class="content-grid">',
      '<div class="panel">',
      '<div class="section-title"><div><h2>Proyectos</h2><p>Mapa operativo de rutas, repos y estado.</p></div><button class="btn" data-route="apps" type="button">Ver todo</button></div>',
      '<div class="app-list">' + state.apps.map(renderAppRow).join("") + "</div>",
      "</div>",
      '<div class="panel">',
      '<div class="section-title"><div><h2>Acciones recientes</h2><p>Actividad operativa del admin.</p></div></div>',
      renderTimeline(),
      "</div>",
      "</section>",
      '<section class="content-grid equal" style="margin-top:18px">',
      '<div class="panel">',
      '<div class="section-title"><div><h2>Acciones rápidas</h2><p>Operá la app seleccionada sin copiar comandos.</p></div>' + appSelect("activeAppSelect") + "</div>",
      renderCommandList(activeApp()),
      "</div>",
      '<div class="panel">',
      '<div class="section-title"><div><h2>App seleccionada</h2><p>Resumen operativo cargado desde la VPS.</p></div><button class="btn" type="button" data-route="help">' + icons.help + " Ayuda</button></div>",
      renderAppDetails(activeApp()),
      "</div>",
      "</section>"
    ].join("");
  }

  function stat(label, value, color, icon) {
    return '<article class="stat-card"><header><span>' + label + '</span><span class="stat-icon ' + color + '">' + icon + '</span></header><strong>' + value + "</strong></article>";
  }

  function avg(key) {
    if (!state.apps.length) return 0;
    return state.apps.reduce(function (sum, item) { return sum + Number(item[key] || 0); }, 0) / state.apps.length;
  }

  function renderAppRow(item) {
    var disabled = actionState.running ? " disabled" : "";
    return [
      '<article class="app-row">',
      '<div class="app-identity"><span class="app-avatar">' + escapeHtml(item.slug.slice(0, 2).toUpperCase()) + '</span><div><strong>' + escapeHtml(item.name) + '</strong><span>' + escapeHtml(item.appId) + "</span></div></div>",
      '<div><strong>' + escapeHtml(publicUrl(item)) + '</strong><div class="meta">' + escapeHtml(item.repo) + "</div></div>",
      '<div class="app-actions"><span class="status-pill ' + item.status + '"><span class="dot"></span>' + statusLabel(item.status) + '</span><button class="btn icon-only" title="Deploy" aria-label="Deploy" data-app-action="deploy" data-slug="' + item.slug + '"' + disabled + '>' + icons.play + '</button><button class="btn icon-only" title="Logs" aria-label="Logs" data-open-logs="' + item.slug + '">' + icons.logs + "</button></div>",
      "</article>"
    ].join("");
  }

  function renderTimeline() {
    if (!state.operations.length) return '<p class="meta">Sin operaciones todavia.</p>';
    return '<div class="timeline">' + state.operations.slice(0, 6).map(function (item) {
      return '<div class="timeline-item"><span class="timeline-pin"></span><div><strong>' + escapeHtml(item.app) + " - " + escapeHtml(item.action) + '</strong><span>' + escapeHtml(item.at || "sin fecha") + " - " + escapeHtml(item.status || "ok") + "</span></div></div>";
    }).join("") + "</div>";
  }

  function appSelect(id) {
    if (!state.apps.length) return '<select class="select" id="' + id + '" aria-label="App activa" disabled><option>Sin apps reales</option></select>';
    return '<select class="select" id="' + id + '" aria-label="App activa">' + state.apps.map(function (item) {
      return '<option value="' + item.slug + '"' + (state.ui.activeApp === item.slug ? " selected" : "") + ">" + item.slug + "</option>";
    }).join("") + "</select>";
  }

  function renderCommandList(item) {
    if (!item) return '<div class="monitor-empty"><span>' + icons.shield + '</span><div><strong>Sin app seleccionada</strong><p>Sincroniza la VPS para habilitar acciones reales.</p></div></div>';
    var commands = [
      ["deploy", "Deploy", "Pull, build, up -d y reload del proxy.", icons.play, "green"],
      ["deploy-local", "Rebuild local", "Reusa el repo actual sin pull.", icons.refresh, "blue"],
      ["status", "Estado", "Consulta Compose y ruta activa.", icons.server, "violet"],
      ["backup", "Backup", "Ejecuta la politica BACKUP_*.", icons.backup, "green"],
      ["stop", "Bajar app", "Detiene sin borrar volumenes.", icons.stop, "amber"],
      ["remove", "Quitar ruta", "Saca la app del proxy.", icons.trash, "amber"]
    ];
    return '<div class="split-actions">' + commands.map(function (entry) {
      return actionButton(entry[0], item, entry[1], entry[2], entry[3], entry[4]);
    }).join("") + "</div>";
  }

  function emptyPanel(title, message, buttonLabel, action) {
    var button = "";
    if (action === "sync") button = '<button class="btn primary" type="button" data-action="sync">' + icons.refresh + " " + buttonLabel + "</button>";
    if (action === "help") button = '<button class="btn" type="button" data-route="help">' + icons.help + " " + buttonLabel + "</button>";
    return [
      '<section class="panel">',
      '<div class="section-title"><div><h2>' + escapeHtml(title) + '</h2><p>' + escapeHtml(message) + "</p></div>" + button + "</div>",
      '<div class="monitor-empty"><span>' + icons.shield + '</span><div><strong>Sin datos operativos cargados</strong><p>Esta vista espera una lectura real desde la VPS. No muestra proyectos de ejemplo.</p></div></div>',
      "</section>"
    ].join("");
  }

  function renderAppDetails(item) {
    if (!item) return '<p class="meta">Sin app seleccionada.</p>';
    return [
      '<div class="detail-grid">',
      '<div><span>Slug</span><strong>' + escapeHtml(item.slug) + '</strong></div>',
      '<div><span>Estado</span><strong>' + statusLabel(item.status) + '</strong></div>',
      '<div><span>URL</span><strong>' + escapeHtml(publicUrl(item)) + '</strong></div>',
      '<div><span>Repositorio</span><strong>' + escapeHtml(item.repo) + '</strong></div>',
      '<div><span>Branch</span><strong>' + escapeHtml(item.branch) + '</strong></div>',
      '<div><span>Upstream</span><strong>' + escapeHtml(item.upstream) + '</strong></div>',
      '<div><span>Contenedores</span><strong>' + escapeHtml((item.containers || []).join(", ") || "sin datos") + '</strong></div>',
      '</div>'
    ].join("");
  }

  function renderApps() {
    if (!state.apps.length) return emptyPanel("Inventario", "Todavia no hay apps reales cargadas desde la VPS.", "Sincronizar", "sync");
    return [
      '<section class="panel">',
      '<div class="section-title"><div><h2>Inventario</h2><p>Cada app conserva slug, app_id, dominio, ruta y upstream.</p></div></div>',
      '<div class="cards-grid">',
      state.apps.map(function (item) {
        var disabled = actionState.running ? " disabled" : "";
        return [
          '<article class="project-card">',
          '<header><div class="card-title"><strong>' + escapeHtml(item.name) + '</strong><span>' + escapeHtml(item.slug) + " · " + escapeHtml(item.appId) + '</span></div><span class="status-pill ' + item.status + '"><span class="dot"></span>' + statusLabel(item.status) + "</span></header>",
          '<div class="detail-grid">',
          "<div><span>URL</span><strong>" + escapeHtml(publicUrl(item)) + "</strong></div>",
          "<div><span>Repo</span><strong>" + escapeHtml(item.repo) + "</strong></div>",
          "<div><span>Branch</span><strong>" + escapeHtml(item.branch) + "</strong></div>",
          "<div><span>Upstream</span><strong>" + escapeHtml(item.upstream) + "</strong></div>",
          "<div><span>Compose</span><strong>" + escapeHtml(item.compose) + "</strong></div>",
          "</div>",
          '<div class="btn-row"><button class="btn primary" type="button" data-app-action="deploy" data-slug="' + item.slug + '"' + disabled + '>' + icons.play + ' Deploy</button><button class="btn" type="button" data-open-logs="' + item.slug + '">' + icons.logs + ' Logs</button><button class="btn" type="button" data-open-database="' + item.slug + '">' + icons.database + ' Datos</button><button class="btn" type="button" data-app-action="backup" data-slug="' + item.slug + '"' + disabled + '>' + icons.backup + ' Backup</button><button class="btn red" type="button" data-app-action="remove" data-slug="' + item.slug + '"' + disabled + '>' + icons.trash + " Ruta</button></div>",
          "</article>"
        ].join("");
      }).join(""),
      "</div>",
      "</section>"
    ].join("");
  }

  function renderLogs() {
    var item = activeApp();
    if (!item) return emptyPanel("Logs", "No hay apps reales cargadas para leer logs.", "Sincronizar", "sync");
    var service = state.ui.logService || "all";
    if (remote.available && logState.key !== item.slug + ":" + (service === "all" ? "" : service) && !logState.loading) {
      window.setTimeout(function () { loadRemoteLogs(item); }, 0);
    }
    var logText = remote.error ? "API no disponible: " + remote.error : "Conecta la VPS para leer logs reales.";
    return [
      '<section class="content-grid">',
      '<div class="panel">',
      '<div class="section-title"><div><h2>Salida</h2><p>' + (remote.available ? "Logs reales leidos desde la VPS." : "Sin lectura real de logs todavia.") + '</p></div><div class="btn-row">' + appSelect("logAppSelect") + '<select class="select" id="logServiceSelect"><option value="all"' + (service === "all" ? " selected" : "") + '>all</option><option value="web"' + (service === "web" ? " selected" : "") + '>web</option><option value="nginx"' + (service === "nginx" ? " selected" : "") + '>nginx</option><option value="api"' + (service === "api" ? " selected" : "") + '>api</option><option value="db"' + (service === "db" ? " selected" : "") + '>db</option></select><button class="btn icon-only" type="button" title="Actualizar logs" aria-label="Actualizar logs" data-refresh-logs>' + icons.refresh + "</button></div></div>",
      '<div class="logs-console"><span class="' + (logState.error ? "err" : "ok") + '">' + escapeHtml(remote.available ? (logState.loading ? "Cargando logs reales..." : logState.error || logState.text || "Sin logs para mostrar.") : logText).replace(/\\n/g, '</span>\\n<span class="' + (logState.error ? "err" : "ok") + '">') + "</span></div>",
      "</div>",
      '<div class="panel">',
      '<div class="section-title"><div><h2>Contexto</h2><p>Servicio, upstream y contenedores asociados.</p></div><button class="btn" type="button" data-route="help">' + icons.help + " Ayuda</button></div>",
      renderAppDetails(item),
      "</div>",
      "</section>"
    ].join("");
  }

  function renderMonitorStatusPanel() {
    var snapshot = monitorState.snapshot;
    if (!snapshot && !monitorState.error && !monitorState.loading) return "";
    var disk = primaryDisk(snapshot);
    var status = monitorState.loading ? "Actualizando" : snapshot && monitorState.error ? "Lectura anterior" : snapshot ? "Lectura real" : "API pendiente";
    var statusClass = snapshot && !monitorState.error ? "running" : monitorState.error ? "idle" : "stopped";
    var hostLabel = snapshot ? snapshot.host.hostname + " - " + snapshot.host.os + (monitorState.error ? " - " + monitorState.error : "") : monitorState.error || "Esperando la primera lectura del API local.";
    return [
      '<section class="panel monitor-status-panel">',
      '<div class="section-title"><div><h2>Servidor</h2><p>' + escapeHtml(hostLabel) + '</p></div><div class="btn-row"><span class="status-pill ' + statusClass + '"><span class="dot"></span>' + status + '</span><button class="btn icon-only" type="button" title="Actualizar" aria-label="Actualizar monitoreo" data-refresh-monitor>' + icons.refresh + "</button></div></div>",
      snapshot ? '<div class="monitor-mini-grid">' + [
        '<div><span>Uptime</span><strong>' + formatDuration(snapshot.host.uptime_seconds) + "</strong></div>",
        '<div><span>Load</span><strong>' + escapeHtml(snapshot.cpu.load_average.join(" / ")) + "</strong></div>",
        '<div><span>RAM libre</span><strong>' + formatBytes(snapshot.memory.available_bytes) + "</strong></div>",
        '<div><span>Disco</span><strong>' + (disk ? formatBytes(disk.available_bytes) + " libre" : "sin dato") + "</strong></div>",
        '<div><span>Docker</span><strong>' + (snapshot.docker.available ? snapshot.docker.running + "/" + snapshot.docker.total : "sin acceso") + "</strong></div>",
        '<div><span>Lectura</span><strong>' + escapeHtml(formatTimestamp(snapshot.generated_at)) + "</strong></div>"
      ].join("") + "</div>" : '<div class="monitor-empty"><span>' + icons.shield + '</span><div><strong>Conecta el API local para ver datos reales.</strong><p>Nginx debe poder hablar con sgdev-admin-control-api en host.docker.internal:9101.</p></div></div>',
      "</section>"
    ].join("");
  }

  function renderMonitorNotice() {
    var tokenSaved = loadAdminApiToken() ? "Token guardado en este navegador" : "Pega SGDEV_ADMIN_API_TOKEN";
    return [
      '<section class="panel monitor-notice">',
      '<div class="section-title"><div><h2>API de monitoreo</h2><p>' + escapeHtml(monitorState.error || "El admin todavia no recibio una lectura real.") + '</p></div><button class="btn" type="button" data-refresh-monitor>' + icons.refresh + " Reintentar</button></div>",
      '<form class="monitor-token-form" id="monitorTokenForm">',
      '<div class="field"><label for="monitorApiToken">Token API</label><input class="input" id="monitorApiToken" name="apiToken" type="password" autocomplete="current-password" placeholder="' + escapeHtml(tokenSaved) + '"></div>',
      '<button class="btn primary" type="submit">' + icons.lock + " Guardar token</button>",
      "</form>",
      '<div style="height:14px"></div><button class="btn" type="button" data-route="help">' + icons.help + " Ver instalacion en Ayuda</button>",
      "</section>"
    ].join("");
  }

  function progressRow(label, percent, meta) {
    var safe = clampPercent(percent);
    return '<div class="progress-row"><header><span>' + escapeHtml(label) + '</span><span>' + formatPercent(safe) + '</span></header><div class="meter"><span style="--value:' + safe + '%"></span></div>' + (meta ? '<p class="meta">' + escapeHtml(meta) + "</p>" : "") + "</div>";
  }

  function renderHostPanel(snapshot) {
    return [
      '<div class="panel">',
      '<div class="section-title"><div><h2>Host Linux</h2><p>Sistema operativo, kernel y carga de la maquina.</p></div><button class="btn icon-only" type="button" title="Actualizar" aria-label="Actualizar monitoreo" data-refresh-monitor>' + icons.refresh + "</button></div>",
      '<div class="detail-grid monitor-detail-grid">',
      '<div><span>Hostname</span><strong>' + escapeHtml(snapshot.host.hostname) + "</strong></div>",
      '<div><span>OS</span><strong>' + escapeHtml(snapshot.host.os) + "</strong></div>",
      '<div><span>Kernel</span><strong>' + escapeHtml(snapshot.host.kernel) + "</strong></div>",
      '<div><span>Arquitectura</span><strong>' + escapeHtml(snapshot.host.architecture) + "</strong></div>",
      '<div><span>CPU cores</span><strong>' + escapeHtml(snapshot.cpu.cores) + "</strong></div>",
      '<div><span>Uptime</span><strong>' + escapeHtml(formatDuration(snapshot.host.uptime_seconds)) + "</strong></div>",
      '<div><span>Load avg</span><strong>' + escapeHtml(snapshot.cpu.load_average.join(" / ")) + "</strong></div>",
      '<div><span>Lectura UTC</span><strong>' + escapeHtml(snapshot.generated_at) + "</strong></div>",
      "</div>",
      "</div>"
    ].join("");
  }

  function renderResourcesPanel(snapshot) {
    var diskRows = snapshot.disks.map(function (disk) {
      return progressRow("Disco " + disk.path, disk.used_percent, formatBytes(disk.used_bytes) + " usados - " + formatBytes(disk.available_bytes) + " libres");
    }).join("");
    return [
      '<div class="panel">',
      '<div class="section-title"><div><h2>Memoria y disco</h2><p>Disponibilidad real del host y rutas operativas.</p></div></div>',
      '<div class="progress-list">',
      progressRow("RAM usada", snapshot.memory.used_percent, formatBytes(snapshot.memory.used_bytes) + " usados - " + formatBytes(snapshot.memory.available_bytes) + " disponibles"),
      progressRow("Swap usada", snapshot.memory.swap_used_percent, formatBytes(snapshot.memory.swap_used_bytes) + " usados - " + formatBytes(snapshot.memory.swap_total_bytes) + " total"),
      diskRows || '<p class="meta">Sin discos configurados para medir.</p>',
      "</div>",
      "</div>"
    ].join("");
  }

  function renderProcessesPanel(snapshot) {
    var processText = snapshot.security.process_args_included ? "Top por CPU, con argumentos completos visibles." : "Top por CPU, con argumentos ocultos para no filtrar secretos.";
    var rows = snapshot.processes.top.map(function (item) {
      return '<tr><td>' + item.pid + '</td><td>' + escapeHtml(item.user) + '</td><td>' + escapeHtml(item.state) + '</td><td>' + formatPercent(item.cpu_percent) + '</td><td>' + formatPercent(item.memory_percent) + '</td><td>' + formatBytes(item.rss_bytes) + '</td><td>' + escapeHtml(item.command) + "</td></tr>";
    }).join("");
    return [
      '<div class="panel">',
      '<div class="section-title"><div><h2>Procesos</h2><p>' + processText + '</p></div><span class="status-pill running"><span class="dot"></span>' + snapshot.processes.count + " procesos</span></div>",
      rows ? '<div class="table-wrap"><table><thead><tr><th>PID</th><th>User</th><th>Estado</th><th>CPU</th><th>RAM</th><th>RSS</th><th>Comando</th></tr></thead><tbody>' + rows + "</tbody></table></div>" : '<p class="meta">No se pudieron leer procesos: ' + escapeHtml(snapshot.processes.error || "sin datos") + "</p>",
      "</div>"
    ].join("");
  }

  function renderDockerPanel(snapshot) {
    if (!snapshot.docker.available) {
      return [
        '<div class="panel">',
        '<div class="section-title"><div><h2>Docker</h2><p>El API no pudo leer Docker en esta lectura.</p></div></div>',
        '<div class="info-tile"><span class="action-icon amber">' + icons.shield + '</span><div><strong>Metricas Docker no disponibles</strong><span>' + escapeHtml(snapshot.docker.error || "El usuario del servicio no tiene acceso a Docker o Docker no esta instalado.") + "</span></div></div>",
        "</div>"
      ].join("");
    }
    var rows = snapshot.docker.containers.map(function (item) {
      var pillClass = item.state === "running" ? "running" : "stopped";
      return '<tr><td>' + escapeHtml(item.name) + '</td><td>' + escapeHtml(item.image) + '</td><td><span class="status-pill ' + pillClass + '"><span class="dot"></span>' + escapeHtml(item.state) + '</span></td><td>' + formatPercent(item.cpu_percent) + '</td><td>' + formatPercent(item.memory_percent) + '</td><td>' + escapeHtml(item.memory_usage || "-") + '</td><td>' + escapeHtml(item.restart_count) + '</td><td>' + escapeHtml(item.compose_project || "-") + "</td></tr>";
    }).join("");
    return [
      '<div class="panel">',
      '<div class="section-title"><div><h2>Docker</h2><p>Contenedores del host, uso instantaneo y proyecto Compose.</p></div><span class="status-pill running"><span class="dot"></span>' + snapshot.docker.running + "/" + snapshot.docker.total + " activos</span></div>",
      rows ? '<div class="table-wrap"><table><thead><tr><th>Contenedor</th><th>Imagen</th><th>Estado</th><th>CPU</th><th>RAM</th><th>Memoria</th><th>Reinicios</th><th>Compose</th></tr></thead><tbody>' + rows + "</tbody></table></div>" : '<p class="meta">Sin contenedores Docker.</p>',
      "</div>"
    ].join("");
  }

  function renderNetworkPanel(snapshot) {
    var rows = snapshot.network.interfaces.map(function (item) {
      return '<tr><td>' + escapeHtml(item.name) + '</td><td>' + formatBytes(item.rx_bytes) + '</td><td>' + escapeHtml(item.rx_packets) + '</td><td>' + formatBytes(item.tx_bytes) + '</td><td>' + escapeHtml(item.tx_packets) + "</td></tr>";
    }).join("");
    return [
      '<div class="panel">',
      '<div class="section-title"><div><h2>Red</h2><p>Acumulados por interfaz desde el arranque.</p></div></div>',
      rows ? '<div class="table-wrap"><table><thead><tr><th>Interfaz</th><th>RX</th><th>Paquetes RX</th><th>TX</th><th>Paquetes TX</th></tr></thead><tbody>' + rows + "</tbody></table></div>" : '<p class="meta">Sin datos de red.</p>',
      "</div>"
    ].join("");
  }

  function renderMetrics() {
    var snapshot = monitorState.snapshot;
    var disk = primaryDisk(snapshot);
    if (!snapshot) {
      return [
        renderMonitorStatusPanel(),
        renderMonitorNotice(),
        '<section class="content-grid" style="margin-top:18px">',
        '<div class="panel">',
        '<div class="section-title"><div><h2>Sin lectura real</h2><p>La vista espera datos de la VPS; no se muestran metricas locales.</p></div></div>',
        '<div class="progress-list">' + state.apps.map(function (item) {
          return progressRow(item.slug + " - CPU", item.cpu, "Memoria " + item.memory + "% - disco " + item.disk + "%");
        }).join("") + "</div>",
        "</div>",
        '<div class="panel">',
        '<div class="section-title"><div><h2>Apps registradas</h2><p>Inventario local del admin.</p></div></div>',
        '<div class="table-wrap"><table><thead><tr><th>App</th><th>Contenedores</th><th>Disco</th><th>Reinicios</th><th>Estado</th></tr></thead><tbody>',
        state.apps.map(function (item) {
          return '<tr><td>' + escapeHtml(item.slug) + '</td><td>' + escapeHtml(item.containers.join(", ")) + '</td><td>' + item.disk + '%</td><td>' + item.restarts + '</td><td><span class="status-pill ' + item.status + '"><span class="dot"></span>' + statusLabel(item.status) + "</span></td></tr>";
        }).join(""),
        "</tbody></table></div>",
        "</div>",
        "</section>"
      ].join("");
    }

    return [
      renderMonitorStatusPanel(),
      '<section class="metric-grid">',
      stat("CPU", formatPercent(snapshot.cpu.usage_percent), "blue", icons.chart),
      stat("RAM disponible", formatBytes(snapshot.memory.available_bytes), "green", icons.database),
      stat("Disco libre", disk ? formatBytes(disk.available_bytes) : "sin dato", "amber", icons.backup),
      stat("Procesos", snapshot.processes.count, "violet", icons.bolt),
      "</section>",
      '<section class="content-grid">',
      renderHostPanel(snapshot),
      renderResourcesPanel(snapshot),
      "</section>",
      '<section class="content-grid single" style="margin-top:18px">',
      renderProcessesPanel(snapshot),
      "</section>",
      '<section class="content-grid single" style="margin-top:18px">',
      renderDockerPanel(snapshot),
      "</section>",
      '<section class="content-grid single" style="margin-top:18px">',
      renderNetworkPanel(snapshot),
      "</section>"
    ].join("");
  }

  function renderDatabase() {
    var item = activeApp();
    if (!item) return emptyPanel("Base de datos", "No hay app real seleccionada para exportar datos.", "Sincronizar", "sync");
    return [
      '<section class="content-grid">',
      '<div class="panel">',
      '<div class="section-title"><div><h2>Excel del proyecto</h2><p>Exporta datos para archivar y reimporta el mismo archivo cuando haga falta.</p></div>' + appSelect("dbAppSelect") + "</div>",
      '<div class="split-actions">',
      '<div class="info-tile"><span class="action-icon green">' + icons.backup + '</span><div><strong>Exportar Excel</strong><span>Receta manual en Ayuda hasta desplegar los scripts DB en la VPS.</span></div></div>',
      '<div class="info-tile"><span class="action-icon blue">' + icons.upload + '</span><div><strong>Importar</strong><span>Usa la receta manual de Ayuda para indicar el archivo .xlsx exacto.</span></div></div>',
      '<div class="info-tile"><span class="action-icon amber">' + icons.refresh + '</span><div><strong>Reemplazar proyecto</strong><span>Modo controlado para refrescar filas de una app específica.</span></div></div>',
      '</div>',
      "</div>",
      '<div class="panel">',
      '<div class="section-title"><div><h2>Alcance de datos</h2><p>Si una tabla tiene app_id, el Excel queda filtrado a la app seleccionada.</p></div></div>',
      '<div class="split-actions">',
      '<div class="info-tile"><span class="action-icon green">' + icons.shield + '</span><div><strong>Seguro por defecto</strong><span>Importar solo inserta; el reemplazo por app_id se pide con --mode replace-project.</span></div></div>',
      '<div class="info-tile"><span class="action-icon blue">' + icons.database + '</span><div><strong>Sin puertos publicos</strong><span>Los scripts entran al cliente psql/mysql dentro del servicio Docker Compose.</span></div></div>',
      '<div class="info-tile"><span class="action-icon violet">' + icons.help + '</span><div><strong>Recetas en Ayuda</strong><span>SQL, variables y comandos quedan documentados en la biblioteca.</span></div></div>',
      "</div>",
      "</div>",
      "</section>"
    ].join("");
  }

  function renderDomains() {
    return [
      '<section class="content-grid">',
      '<div class="panel">',
      '<div class="section-title"><div><h2>Instancia</h2><p>Configuracion detectada desde la VPS.</p></div><button class="btn icon-only" type="button" title="Actualizar" aria-label="Actualizar VPS" data-action="sync">' + icons.refresh + "</button></div>",
      '<div class="detail-grid">',
      '<div><span>Dominio admin</span><strong>' + escapeHtml(state.settings.controlDomain) + '</strong></div>',
      '<div><span>Ruta admin</span><strong>' + escapeHtml(state.settings.adminPath) + '</strong></div>',
      '<div><span>Red Docker</span><strong>' + escapeHtml(state.settings.proxyNetwork) + '</strong></div>',
      '<div><span>Webhook path</span><strong>' + escapeHtml(state.settings.deployHookPath) + '</strong></div>',
      '<div><span>Apps root</span><strong>' + escapeHtml(state.settings.appsRoot) + '</strong></div>',
      '<div><span>Config root</span><strong>' + escapeHtml(state.settings.configRoot) + '</strong></div>',
      '</div>',
      "</div>",
      '<div class="panel">',
      '<div class="section-title"><div><h2>Mapa de rutas</h2><p>Hosts y subrutas conviviendo en el mismo Nginx.</p></div></div>',
      '<div class="table-wrap"><table><thead><tr><th>App</th><th>Host</th><th>Ruta</th><th>Destino</th></tr></thead><tbody>',
      state.apps.map(function (item) {
        return '<tr><td>' + item.slug + '</td><td>' + item.domain + '</td><td>' + item.path + '</td><td>' + escapeHtml(item.upstream) + "</td></tr>";
      }).join(""),
      "</tbody></table></div>",
      '<div style="height:14px"></div>',
      '<div class="info-tile"><span class="action-icon blue">' + icons.help + '</span><div><strong>Plantillas Nginx en Ayuda</strong><span>Las reglas exactas del proxy quedan como referencia, separadas de la operación diaria.</span></div></div>',
      "</div>",
      "</section>"
    ].join("");
  }

  function renderCicd() {
    var item = activeApp();
    if (!item) return emptyPanel("CI/CD", "No hay app real seleccionada para ejecutar pipelines.", "Sincronizar", "sync");
    var hook = "https://" + state.settings.controlDomain + state.settings.deployHookPath + item.slug;
    return [
      '<section class="content-grid">',
      '<div class="panel">',
      '<div class="section-title"><div><h2>Pipeline manual</h2><p>Botones traducidos a scripts versionados.</p></div>' + appSelect("cicdAppSelect") + "</div>",
      '<div class="split-actions">',
      actionButton("deploy", item, "Deploy", "Pull, build, up -d y reload Nginx.", icons.play, "green"),
      actionButton("deploy-local", item, "Rebuild local", "Reusa el repo actual sin git pull.", icons.refresh, "blue"),
      actionButton("backup", item, "Backup", "Ejecuta BACKUP_COMMAND, volumenes o paths.", icons.backup, "green"),
      actionButton("stop", item, "Stop", "Baja compose sin borrar volumenes.", icons.stop, "amber"),
      actionButton("remove", item, "Quitar ruta", "Saca la app del proxy.", icons.trash, "amber"),
      actionButton("remove-stop", item, "Baja completa", "Quita ruta y detiene contenedores.", icons.trash, "red"),
      "</div>",
      "</div>",
      '<div class="panel">',
      '<div class="section-title"><div><h2>Webhook</h2><p>Entrada para GitHub o un boton externo.</p></div><button class="btn" type="button" data-route="help">' + icons.help + " Ayuda</button></div>",
      '<div class="detail-grid">',
      '<div><span>URL</span><strong>' + escapeHtml(hook) + '</strong></div>',
      '<div><span>App</span><strong>' + escapeHtml(item.slug) + '</strong></div>',
      '<div><span>Branch</span><strong>' + escapeHtml(item.branch) + '</strong></div>',
      '<div><span>Repo</span><strong>' + escapeHtml(item.repo) + '</strong></div>',
      '</div>',
      '<div style="height:14px"></div>',
      '<div class="info-tile"><span class="action-icon violet">' + icons.cicd + '</span><div><strong>Workflow y YAML</strong><span>La plantilla completa esta en Ayuda para no mezclar documentación con operación.</span></div></div>',
      "</div>",
      "</section>"
    ].join("");
  }

  function actionButton(action, item, title, description, icon, color) {
    if (!item) return "";
    var disabled = actionState.running ? " disabled" : "";
    return '<button class="action-tile" type="button" data-app-action="' + action + '" data-slug="' + item.slug + '"' + disabled + '><span class="action-icon ' + color + '">' + icon + '</span><div><strong>' + title + '</strong><span>' + description + '</span></div></button>';
  }

  function renderHelp() {
    var section = helpGroups.find(function (group) { return group.id === state.ui.helpSection; }) || helpGroups[0];
    if (section.keys.indexOf(state.ui.helpTemplate) < 0) {
      state.ui.helpTemplate = section.keys[0];
    }
    var current = state.ui.helpTemplate || section.keys[0];
    var template = helpTemplates[current] || helpTemplates.checklist;
    return [
      '<section class="panel">',
      '<div class="section-title"><div><h2>Biblioteca operativa</h2><p>Comandos, plantillas y recetas separados de la consola diaria.</p></div></div>',
      '<div class="tabbar">',
      helpGroups.map(function (group) {
        return '<button class="tab ' + (group.id === section.id ? "active" : "") + '" type="button" data-help-section="' + group.id + '">' + group.label + "</button>";
      }).join(""),
      "</div>",
      '<div class="template-grid">',
      '<div class="template-list">',
      section.keys.map(function (key) {
        return '<button type="button" class="' + (key === current ? "active" : "") + '" data-help-template="' + key + '">' + helpTemplates[key].title + "</button>";
      }).join(""),
      "</div>",
      '<div>' + codeCard(template.title, template.body) + "</div>",
      "</div>",
      "</section>"
    ].join("");
  }

  function toast(message) {
    var previous = document.querySelector(".toast");
    if (previous) previous.remove();
    var node = document.createElement("div");
    node.className = "toast";
    node.textContent = message;
    document.body.appendChild(node);
    window.setTimeout(function () {
      node.remove();
    }, 2600);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { toast("Copiado"); });
      return;
    }
    var input = document.createElement("textarea");
    input.value = text;
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    input.remove();
    toast("Copiado");
  }

  app.addEventListener("click", async function (event) {
    var routeButton = event.target.closest("[data-route]");
    if (routeButton) {
      navigate(routeButton.getAttribute("data-route"));
      return;
    }

    var copyButton = event.target.closest("[data-copy]");
    if (copyButton) {
      copyText(copyButton.getAttribute("data-copy"));
      return;
    }

    var refreshMonitorButton = event.target.closest("[data-refresh-monitor]");
    if (refreshMonitorButton) {
      monitorState.lastFetch = 0;
      requestMonitorSnapshot(true);
      return;
    }

    var refreshLogsButton = event.target.closest("[data-refresh-logs]");
    if (refreshLogsButton) {
      logState.key = "";
      await loadRemoteLogs(activeApp());
      return;
    }

    var helpButton = event.target.closest("[data-help-template]");
    if (helpButton) {
      state.ui.helpTemplate = helpButton.getAttribute("data-help-template");
      saveState();
      render();
      return;
    }

    var helpSectionButton = event.target.closest("[data-help-section]");
    if (helpSectionButton) {
      var sectionId = helpSectionButton.getAttribute("data-help-section");
      var group = helpGroups.find(function (item) { return item.id === sectionId; }) || helpGroups[0];
      state.ui.helpSection = group.id;
      state.ui.helpTemplate = group.keys[0];
      saveState();
      render();
      return;
    }

    var openLogsButton = event.target.closest("[data-open-logs]");
    if (openLogsButton) {
      state.ui.activeApp = openLogsButton.getAttribute("data-open-logs");
      saveState();
      navigate("logs");
      return;
    }

    var openDatabaseButton = event.target.closest("[data-open-database]");
    if (openDatabaseButton) {
      state.ui.activeApp = openDatabaseButton.getAttribute("data-open-database");
      saveState();
      navigate("database");
      return;
    }

    var actionButton = event.target.closest("[data-app-action]");
    if (actionButton) {
      var item = appBySlug(actionButton.getAttribute("data-slug"));
      var action = actionButton.getAttribute("data-app-action");
      try {
        await runRemoteAction(action, item);
      } catch (error) {
        toast("Error ejecutando en VPS: " + (error.message || error));
      }
      return;
    }

    var syncButton = event.target.closest('[data-action="sync"]');
    if (syncButton) {
      monitorState.lastFetch = 0;
      await syncRemoteState(false);
      return;
    }

    var logoutButton = event.target.closest('[data-action="logout"]');
    if (logoutButton) {
      saveSession(null);
      navigate("login");
    }
  });

  app.addEventListener("submit", function (event) {
    if (event.target.id === "loginForm") {
      event.preventDefault();
      var form = new FormData(event.target);
      var loginToken = String(form.get("token") || "").trim();
      saveAdminApiToken(loginToken);
      saveSession({ email: form.get("email"), token: loginToken, at: nowStamp() });
      navigate("dashboard");
      syncRemoteState(false);
      return;
    }

    if (event.target.id === "monitorTokenForm") {
      event.preventDefault();
      var tokenForm = new FormData(event.target);
      saveAdminApiToken(String(tokenForm.get("apiToken") || "").trim());
      monitorState.lastFetch = 0;
      toast("Token de monitoreo guardado");
      requestMonitorSnapshot(true);
      return;
    }

  });

  app.addEventListener("change", async function (event) {
    if (event.target.id === "mobileNav") {
      navigate(event.target.value);
      return;
    }

    if (["activeAppSelect", "logAppSelect", "dbAppSelect", "cicdAppSelect"].indexOf(event.target.id) >= 0) {
      state.ui.activeApp = event.target.value;
      saveState();
      render();
      if (event.target.id === "logAppSelect") {
        logState.key = "";
        await loadRemoteLogs(activeApp());
      }
      return;
    }

    if (event.target.id === "logServiceSelect") {
      state.ui.logService = event.target.value;
      saveState();
      render();
      logState.key = "";
      await loadRemoteLogs(activeApp());
    }
  });

  window.setInterval(function () {
    if (session && isMonitorRoute(currentRoute())) requestMonitorSnapshot(false);
  }, MONITOR_REFRESH_MS);

  window.addEventListener("popstate", render);
  render();
})();
