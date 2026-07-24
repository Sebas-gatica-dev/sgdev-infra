# CI/CD con GitHub dentro de la VM

## Modelo recomendado

Para uso de prueba, el flujo mas simple es:

```text
push local -> GitHub -> webhook a la VM -> app-deploy.sh -> git pull -> docker compose up -d --build
```

No necesitas Docker Hub ni Artifact Registry. La VM construye las imagenes.

## Instalar el servicio

En la VM:

```bash
cd /opt/sgdev-infra
sudo ./scripts/install-cicd.sh
```

Esto crea un servicio systemd:

```bash
systemctl status sgdev-webhookd.service
```

El servicio escucha solo en `127.0.0.1:9000`. Nginx lo expone hacia afuera en:

```text
http://IP_VM/__deploy/github/<slug>
```

## Configurar un proyecto

Ejemplo para JanoAI:

```bash
sudo cp /opt/sgdev-infra/examples/cicd/janoai.env.example /etc/sgdev-infra/cicd/janoai.env
sudo nano /etc/sgdev-infra/cicd/janoai.env
```

Para los otros proyectos es igual, cambiando el slug:

```bash
sudo cp /opt/sgdev-infra/examples/cicd/egregor.env.example /etc/sgdev-infra/cicd/egregorai.env
sudo cp /opt/sgdev-infra/examples/cicd/sgdev-portfolio.env.example /etc/sgdev-infra/cicd/portfolio.env
```

Contenido esperado:

```bash
GITHUB_WEBHOOK_SECRET=un-secreto-largo-random
GITHUB_REPOSITORY=owner/janoai
GITHUB_BRANCH=main
DEPLOY_SCRIPT=/opt/sgdev-infra/scripts/app-deploy.sh
```

Generar un secreto:

```bash
openssl rand -hex 32
```

## Configurar GitHub

En el repo de GitHub:

1. Settings.
2. Webhooks.
3. Add webhook.
4. Payload URL:
   `http://IP_VM/__deploy/github/janoai`
5. Content type: `application/json`.
6. Secret: el mismo valor de `GITHUB_WEBHOOK_SECRET`.
7. Events: solo `push`.
8. Active: habilitado.

Cuando hagas push a `main`, la VM ejecuta:

```bash
/opt/sgdev-infra/scripts/app-deploy.sh janoai
```

Para `portfolio`, ese deploy carga `/etc/sgdev-infra/apps/portfolio.env` antes
del `.env` del repo. Mantener ahi `VITE_BASE_PATH=/portfolio/` y el mismo valor
de `PORTFOLIO_USAGE_ADMIN_TOKEN` que usa
`SGDEV_PORTFOLIO_USAGE_ADMIN_TOKEN` en el control API.

## Logs

```bash
journalctl -u sgdev-webhookd.service -f
tail -f /var/log/sgdev-infra/janoai-deploy.log
```

## Seguridad minima

- Usar secreto largo por proyecto.
- Usar repos privados al principio.
- No exponer claves `.env` en Git.
- No aceptar ramas que no sean `main` o la rama configurada.
- No usar este webhook para ejecutar comandos arbitrarios.
- Con dominio y HTTPS, cambiar el webhook a `https://...`.

## Alternativa: deploy manual

Si todavia no queres webhook:

```bash
cd /opt/sgdev-infra
./scripts/app-deploy.sh janoai
```

Ese comando ya hace `git pull`, build, up y reload de Nginx.

## Workflow manual `Deploy app`

En GitHub Actions, `Use workflow from` elige la rama de SgInfra que contiene el
workflow. Para operar aplicaciones se usa el campo `slug`:

| Objetivo | `slug` | `provision_from_example` |
| --- | --- | --- |
| Portfolio principal | `portfolio` | `false` |
| ArgentiCommerce | `argenticommerce` | `false` |
| Portfolio de Soff, primera vez | `soff-portfolio` | `true` |
| Portfolio de Soff, actualizaciones | `soff-portfolio` | `false` |
| Solo infraestructura, admin y proxy | `infra` o `admin` | `false` |

`provision_from_example=true` solo actua cuando todavía no existe
`/etc/sgdev-infra/apps/<slug>.env`. El alta se toma de un manifiesto versionado
en `examples/apps/<slug>.env.example`; no reemplaza configuraciones existentes.

`no_pull=true` reconstruye la revisión que ya está en la VPS. Para traer el
último commit de la aplicación se debe dejar en `false`.

El manifiesto `examples/apps/soff-portfolio.env.example` también dispara el
workflow al cambiar en `main`. Esto permite que su primera incorporación se
registre y despliegue automáticamente; los cambios normales del código de la
aplicación se siguen desplegando manualmente con `slug=soff-portfolio`.
