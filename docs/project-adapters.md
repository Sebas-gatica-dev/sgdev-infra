# Adaptadores por proyecto

## Regla comun

Cada proyecto debe cumplir esto para convivir con el proxy:

1. No publicar puertos hacia internet.
2. Conectar el servicio web principal a la red externa `sgdev-proxy`.
3. Darle un alias unico al servicio web.
4. Configurar el frontend para vivir bajo su path si se usa IP con rutas.

## JanoAI

Ruta local actual:

```text
C:\Users\CFOTech\Documents\dev\JanoAI
```

En la VM:

```text
/opt/apps/janoai/repo
```

JanoAI ya tiene `compose.prod.yml` con un Nginx interno. Para usarlo detras del
proxy compartido:

- Quitar la publicacion `80:80` y `443:443` del Nginx interno.
- Exponer solo `80` dentro de Docker.
- Conectar el servicio `nginx` a `sgdev-proxy`.
- Usar alias `janoai-nginx`.

Hay un override de ejemplo:

```text
examples/project-compose/janoai.compose.proxy.override.yml
```

Para usarlo desde los scripts, definir en
`/etc/sgdev-infra/apps/janoai.env`:

```bash
COMPOSE_FILES="compose.prod.yml /opt/sgdev-infra/examples/project-compose/janoai.compose.proxy.override.yml"
```

Configuracion de app:

```bash
sudo cp /opt/sgdev-infra/examples/apps/janoai.env.example /etc/sgdev-infra/apps/janoai.env
sudo nano /etc/sgdev-infra/apps/janoai.env
```

Importante para `/janoai`: Next.js debe generar links y assets bajo ese prefijo.
Si no, se veran requests a `/_next/...` en la raiz de la IP. Para una demo,
podes ajustar `basePath: '/janoai'` y revisar rutas BFF/API.

## EgregorAI

Ruta local actual:

```text
C:\Users\CFOTech\Documents\dev\EgregorAI
```

En la VM:

```text
/opt/apps/egregorai/repo
```

EgregorAI tiene varios servicios y hoy publica puertos de desarrollo. En VPS:

- Quitar puertos publicados de API, DB, Selenium, local AI y web research.
- Conectar `egregor-web` a `sgdev-proxy`.
- Mantener `egregor-api`, DB y herramientas en redes internas del proyecto.
- Usar upstream `http://egregor-web:80`.

Hay un override de ejemplo:

```text
examples/project-compose/egregor.compose.proxy.override.yml
```

Para usarlo desde los scripts, definir en
`/etc/sgdev-infra/apps/egregorai.env`:

```bash
COMPOSE_FILES="docker-compose.yml /opt/sgdev-infra/examples/project-compose/egregor.compose.proxy.override.yml"
```

Para `/egregorai`, el frontend Vite debe usar base path:

```ts
// vite.config.ts
export default defineConfig({
  base: '/egregorai/',
})
```

Tambien revisar llamadas a `/api`: si el proxy externo recibe
`/egregorai/api/...`, el Nginx interno debe reenviarlo correctamente al backend.

## SG Dev Portfolio

Ruta local actual:

```text
C:\Users\CFOTech\Documents\New project
```

En la VM:

```text
/opt/apps/portfolio/repo
```

Este proyecto ya trae `docker-compose.yml` con frontend, backend, DB y un Nginx
interno. Para publicar bajo `/portfolio`, compilar el frontend con
`VITE_BASE_PATH=/portfolio/`.

La variante actual del portfolio tambien levanta un modelo local gratuito con
Ollama/FastAPI. No necesita publicarse al proxy compartido: queda en la red
interna del compose del portfolio y el backend lo consume como
`http://free-model:8795`.

Configurar:

```bash
sudo cp /opt/sgdev-infra/examples/apps/sgdev-portfolio.env.example /etc/sgdev-infra/apps/portfolio.env
sudo nano /etc/sgdev-infra/apps/portfolio.env
```

En el `.env` runtime del repo del portfolio o en variables equivalentes del
compose, activar:

```bash
PORTFOLIO_FREE_MODEL_ENABLED=true
PORTFOLIO_FREE_MODEL_NAME=qwen3:0.6b
VITE_BASE_PATH=/portfolio/
```

Antes de subir este proyecto a GitHub, revisar que no haya claves reales en
`application.properties`, `.env` o archivos similares. Las claves deben venir
siempre por variables de entorno.

## Agregar otro proyecto

Crear repo:

```bash
sudo mkdir -p /opt/apps/nuevo-proyecto
sudo git clone URL_REPO /opt/apps/nuevo-proyecto/repo
```

Crear config:

```bash
sudo /opt/sgdev-infra/scripts/app-new.sh \
  nuevo-proyecto \
  /opt/apps/nuevo-proyecto/repo \
  http://nuevo-proyecto-web:80 \
  /nuevo-proyecto \
  compose.yml \
  .env
```

Desplegar:

```bash
cd /opt/sgdev-infra
./scripts/app-deploy.sh nuevo-proyecto
```

## Remover un proyecto

Sacar del proxy:

```bash
./scripts/app-remove.sh egregor
```

Sacar del proxy y detener contenedores:

```bash
./scripts/app-remove.sh egregor --stop
```

Esto no borra datos ni volumenes.
