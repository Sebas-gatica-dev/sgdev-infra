# Runbook operativo

Este archivo es la guia corta para operar la VPS, levantar proyectos nuevos y
modificar el gateway `sgdev.com.ar` sin tener que redescubrir la estructura del
repo cada vez.

## Diagnostico actual

- La arquitectura esta bien orientada para muchos proyectos chicos o medianos:
  una VPS, Docker Compose por proyecto y un Nginx compartido como unica entrada
  publica.
- El proxy central publica solo `80` y `443`; las apps deben vivir atras de la
  red Docker externa `sgdev-proxy`.
- El dominio configurado es `sgdev.com.ar`, la VPS documentada es
  `143.95.217.87` y el SSH documentado usa el puerto `22022`.
- El portfolio ya tiene configuracion de ejemplo para publicarse en
  `/portfolio` con upstream `http://portfolio-nginx:80`.
- La raiz `/` ahora redirige temporalmente a `/portfolio/` con `302`, porque la
  intencion actual es que `https://sgdev.com.ar` lleve al portfolio.
- Para crecer a muchos proyectos, el punto mas importante es que cada frontend
  soporte su base path (`/portfolio/`, `/egregorai/`, etc.) o, mas adelante,
  pasar a subdominios.

## Riesgos y pendientes

- `proxy/nginx/conf.d/ssl.conf` se genera en la VPS al correr
  `scripts/install-https.sh` y no esta versionado. Si ya existe HTTPS en el
  server, despues de cambiar la plantilla hay que regenerarlo o editarlo en la
  VPS y recargar Nginx.
- Los secretos deben quedar fuera del repo: `.env`, `terraform.tfvars`,
  `terraform.tfstate`, claves SSH y passwords.
- El estado local de Terraform esta ignorado por Git, pero si se empieza a
  operar con mas frecuencia conviene moverlo a un backend remoto o cuidar muy
  bien la copia local.
- Hay monitoreo basico del host con `sgdev-admin-api` y acciones manuales con
  `sgdev-admin-control-api`, pero todavia no hay alertas, historial persistente
  ni limites de recursos por contenedor. Para muchos proyectos activos conviene
  agregar esas capas.
- El routing por path exige disciplina: si una app genera assets absolutos como
  `/assets/...` o `/_next/...`, puede romperse o pisar rutas de otras apps.

## Entrar a la VPS

Desde una terminal:

```bash
ssh -p 22022 root@143.95.217.87
```

Desde Termius:

```text
Host: 143.95.217.87
Port: 22022
Username: root
Authentication: SSH key
```

Usar clave SSH siempre que sea posible. No copiar claves privadas, passwords ni
contenido de `.env` en chats, issues o commits.

## Carpetas importantes

```text
/opt/sgdev-infra
/opt/apps/<slug>/repo
/etc/sgdev-infra/apps/<slug>.env
/etc/sgdev-infra/cicd/<slug>.env
/opt/backups/<slug>
```

La rutina normal empieza en:

```bash
cd /opt/sgdev-infra
git pull
./scripts/app-status.sh
```

## Comandos diarios

```bash
# Ver proxy y apps registradas
./scripts/app-status.sh

# Ver estado de una app
./scripts/app-status.sh portfolio

# Ver logs
./scripts/app-logs.sh portfolio

# Deploy con git pull, build y reload del proxy
./scripts/app-deploy.sh portfolio

# Deploy sin git pull
./scripts/app-deploy.sh portfolio --no-pull

# Detener una app sin borrar volumenes
./scripts/app-stop.sh portfolio

# Sacar una app del proxy sin borrar datos
./scripts/app-remove.sh portfolio

# Sacar una app del proxy y detenerla
./scripts/app-remove.sh portfolio --stop

# Backup si la app tiene BACKUP_* configurado
./scripts/app-backup.sh portfolio

# Exportar datos de la base a Excel
./scripts/app-db-export-excel.sh portfolio

# Reinsertar un Excel exportado
./scripts/app-db-import-excel.sh portfolio /opt/backups/portfolio/portfolio-db-YYYYMMDDTHHMMSSZ.xlsx
```

## Admin web

La consola estatica queda publicada en:

```text
https://sgdev.com.ar/admin
```

Nginx redirige `/admin` a `/admin/login/` y sirve las rutas internas desde
`proxy/www/admin/index.html`. En la VPS, despues de actualizar el repo:

```bash
cd /opt/sgdev-infra
git pull
./scripts/proxy-reload.sh
```

Para activar metricas reales de la maquina Linux:

```bash
cd /opt/sgdev-infra
sudo chmod +x scripts/*.sh
sudo ./scripts/install-admin-api.sh
./scripts/proxy-reload.sh
sudo grep SGDEV_ADMIN_API_TOKEN /etc/sgdev-infra/admin-api.env
```

Si HTTPS ya estaba activo antes de este cambio, regenerar `ssl.conf` con
`scripts/install-https.sh` para que `/admin/api/` quede tambien en el server
block TLS.

El instalador deja dos servicios locales:

- `sgdev-admin-api.service` escucha en `127.0.0.1:9100`; Nginx lo expone bajo
  `/admin/api/` como monitor read-only legacy.
- `sgdev-admin-control-api.service` escucha en `127.0.0.1:9101`; Nginx lo
  expone bajo `/admin-api/` para que la consola ejecute acciones reales contra
  scripts versionados.

Pegar el valor de `SGDEV_ADMIN_API_TOKEN` en el login del admin. El control API
solo acepta acciones cerradas: deploy, rebuild sin pull, status, backup, stop,
remove, alta guiada de apps, export DB Excel y administracion de tokens OpenAI
del portfolio. WordPress e import DB siguen como recetas manuales en Ayuda.

Para administrar tokens OpenAI del portfolio desde `/admin`, configurar en el
portfolio `PORTFOLIO_USAGE_ADMIN_TOKEN` y en el control API
`SGDEV_PORTFOLIO_USAGE_ADMIN_TOKEN` con el mismo valor. La URL del backend se
lee desde `SGDEV_PORTFOLIO_API_BASE_URL` y suele ser
`https://sgdev.com.ar/portfolio/api`.

El portfolio refactorizado mantiene estas rutas externas, aunque internamente el
backend Java ahora este dividido por dominios:

```text
GET  /portfolio/api/portfolio/health
GET  /portfolio/api/admin/usage/ips
POST /portfolio/api/admin/usage/grant
POST /portfolio/api/agent/chat/stream
POST /portfolio/api/agent/document/summary
```

Comandos utiles:

```bash
systemctl status sgdev-admin-api.service
systemctl status sgdev-admin-control-api.service
journalctl -u sgdev-admin-api.service -f
journalctl -u sgdev-admin-control-api.service -f
curl -H "X-SGDEV-Admin-Token: TOKEN" http://127.0.0.1:9100/v1/snapshot
curl -H "Authorization: Bearer TOKEN" http://127.0.0.1:9101/state
curl -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action":"status","slug":"portfolio"}' \
  http://127.0.0.1:9101/actions
```

Si HTTPS ya esta generado, recordar que `proxy/nginx/conf.d/ssl.conf` se
reescribe desde `proxy/nginx/templates/ssl.conf.template` al correr
`scripts/install-https.sh`.

## Archivar datos de un proyecto en Excel

Cuando una app empiece a ocupar demasiado espacio en la DB, exportar primero sus
datos a Excel:

```bash
cd /opt/sgdev-infra
./scripts/app-db-export-excel.sh portfolio
```

El archivo queda en:

```text
/opt/backups/portfolio/portfolio-db-YYYYMMDDTHHMMSSZ.xlsx
```

Antes de borrar datos productivos, descargar o copiar ese archivo fuera de la
VPS y abrirlo para validar que tenga las tablas esperadas. Si la base es
compartida y las tablas tienen `app_id`, el export filtra por el `APP_ID` del
proyecto; las tablas sin `app_id` se exportan completas.

Para restaurar datos desde el Excel:

```bash
./scripts/app-db-import-excel.sh portfolio /opt/backups/portfolio/portfolio-db-YYYYMMDDTHHMMSSZ.xlsx
```

La restauracion por defecto solo inserta filas. Para reemplazar datos antiguos
del mismo proyecto en tablas con `app_id`:

```bash
./scripts/app-db-import-excel.sh portfolio /opt/backups/portfolio/portfolio-db-YYYYMMDDTHHMMSSZ.xlsx --mode replace-project
```

Si el script no detecta la DB, agregar estos campos al archivo
`/etc/sgdev-infra/apps/<slug>.env`:

```bash
DB_EXCEL_ENGINE=postgres
DB_EXCEL_SERVICE=db
DB_EXCEL_DATABASE=app
DB_EXCEL_USER=app
DB_EXCEL_APP_ID_COLUMN=app_id
```

Ese mismo archivo de app tambien se pasa a Docker Compose antes del `.env` del
repo. Usarlo para defaults de infra como `VITE_BASE_PATH`, `PUBLIC_APP_URL` o
`PORTFOLIO_USAGE_ADMIN_TOKEN`; dejar secretos especificos del runtime en el
`.env` del proyecto cuando se prefiera sobrescribirlos por deploy.

Para WordPress creado con `scripts/app-new-wordpress.sh`, esos campos quedan
generados apuntando a MariaDB.

## Levantar un proyecto nuevo

Elegir un slug corto y estable, por ejemplo `miapp`. Ese slug se usa para la
ruta publica, nombres de archivos y comandos.

```bash
sudo mkdir -p /opt/apps/miapp
sudo git clone URL_DEL_REPO /opt/apps/miapp/repo
```

El compose del proyecto debe cumplir estas reglas:

- El servicio web principal no publica puertos con `ports`.
- El servicio web expone su puerto solo dentro de Docker con `expose`.
- El servicio web se conecta a la red externa `sgdev-proxy`.
- El servicio web tiene un alias unico, por ejemplo `miapp-web`.
- Bases de datos, Redis y servicios internos quedan en redes internas del
  proyecto.

Crear la configuracion del gateway:

```bash
cd /opt/sgdev-infra
sudo ./scripts/app-new.sh \
  miapp \
  /opt/apps/miapp/repo \
  http://miapp-web:80 \
  /miapp \
  compose.yml \
  .env
```

Editar el archivo generado:

```bash
sudo nano /etc/sgdev-infra/apps/miapp.env
```

Campos clave:

```bash
APP_SLUG=miapp
APP_PATH=/miapp
APP_UPSTREAM=http://miapp-web:80
REPO_DIR=/opt/apps/miapp/repo
COMPOSE_FILES="compose.yml"
ENV_FILE=.env
BRANCH=main
GIT_REMOTE_URL=https://github.com/owner/miapp.git
STRIP_PREFIX=true
CLIENT_MAX_BODY_SIZE=25m
PROXY_READ_TIMEOUT=120s
```

Usar `STRIP_PREFIX=true` si la app debe recibir `/` cuando el usuario entra a
`/miapp/`. Usar `STRIP_PREFIX=false` si la app esta preparada para recibir el
prefijo completo `/miapp/...`.

Desplegar:

```bash
./scripts/app-deploy.sh miapp
```

Probar:

```bash
curl -I http://127.0.0.1/miapp/
```

## Levantar WordPress

Para un WordPress rapido y repetible, usar la receta de Ayuda del admin o el
script:

```bash
sudo env WORDPRESS_SITE_TITLE="Blog SGDEV" \
  WORDPRESS_ADMIN_EMAIL="admin@sgdev.com.ar" \
  bash ./scripts/app-new-wordpress.sh blog sgdev.com.ar /blog
```

Esto crea:

```text
/opt/apps/blog/repo/compose.yml
/opt/apps/blog/repo/.env
/opt/apps/blog/repo/wp-content
/etc/sgdev-infra/apps/blog.env
```

Luego revisar secretos y desplegar:

```bash
sudo nano /opt/apps/blog/repo/.env
./scripts/app-deploy.sh blog --no-pull
```

Si existe un repo de tema/plugin o `wp-content`, se puede pasar como cuarto
argumento:

```bash
sudo bash ./scripts/app-new-wordpress.sh blog sgdev.com.ar /blog https://github.com/owner/wp-content.git main
```

Con el proxy actual, `APP_PATH` no puede ser `/`; usar una subruta como
`/blog`. Para WordPress publico en la raiz de un dominio dedicado
(`blog.sgdev.com.ar/`) conviene agregar server blocks por host en Nginx antes de
publicarlo asi, porque WordPress suele ser sensible a URLs absolutas, admin y
plugins.

## Frontends bajo path

Para Vite:

```ts
export default defineConfig({
  base: '/miapp/',
})
```

Para Next.js:

```js
const nextConfig = {
  basePath: '/miapp',
}
module.exports = nextConfig
```

Si esto molesta demasiado para varias apps, el siguiente paso natural es pasar a
subdominios como `miapp.sgdev.com.ar` o `portfolio.sgdev.com.ar`.

## Redirect de sgdev.com.ar a portfolio

El redirect actual esta en dos lugares:

```text
proxy/nginx/conf.d/default.conf
proxy/nginx/templates/ssl.conf.template
```

La regla es:

```nginx
location = / {
    return 302 /portfolio/;
}
```

Para cambiar el destino, editar ambos archivos y reemplazar `/portfolio/` por
la nueva ruta. Por ejemplo:

```nginx
location = / {
    return 302 /miapp/;
}
```

Usar `302` mientras sea una decision temporal. Cuando la raiz definitiva este
clara, se puede cambiar a `301`.

Aplicar el cambio en la VPS si solo esta activo HTTP:

```bash
cd /opt/sgdev-infra
git pull
./scripts/proxy-reload.sh
```

Si HTTPS ya esta activo, el archivo generado `proxy/nginx/conf.d/ssl.conf`
probablemente tenga la regla anterior. Regenerarlo con:

```bash
sudo ./scripts/install-https.sh sebasdeveloperlife@gmail.com sgdev.com.ar www.sgdev.com.ar
```

Ese script vuelve a escribir `ssl.conf` desde la plantilla y recarga Nginx.

Luego validar:

```bash
curl -I https://sgdev.com.ar/
curl -I https://sgdev.com.ar/portfolio/
```

## Checklist antes de sumar muchas apps

- Cada app tiene slug, path y upstream claros.
- Ninguna DB publica puertos a internet.
- Cada app tiene `.env` propio en la VPS.
- Cada app tiene backup configurado si guarda datos.
- Cada frontend fue probado bajo su path publico real.
- El proxy responde `nginx -t` antes de recargar.
- Hay una decision consciente entre path routing y subdominios.
