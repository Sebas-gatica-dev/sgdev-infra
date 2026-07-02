# Terraform y GitHub Actions

Este repo administra el gateway `sgdev.com.ar` en la VPS `143.95.217.87`.

## Flujo recomendado

```text
git push -> GitHub Actions Terraform plan
workflow_dispatch apply -> prepara/actualiza VPS y gateway
workflow_dispatch deploy-app -> ejecuta /opt/sgdev-infra/scripts/app-deploy.sh portfolio
```

Terraform no guarda secretos en el repo. Usa variables de entorno locales o
GitHub Secrets.

## Secrets necesarios en GitHub

En `Settings > Secrets and variables > Actions`:

```text
SGDEV_VPS_HOST=143.95.217.87
SGDEV_SSH_PORT=22022
SGDEV_SSH_USER=root
SGDEV_DOMAIN=sgdev.com.ar
SGDEV_INFRA_REPO_URL=https://github.com/Sebas-gatica-dev/sgdev-infra.git
SGDEV_PORTFOLIO_REPO_URL=https://github.com/Sebas-gatica-dev/sgdev-porfolio.git
SGDEV_SSH_PRIVATE_KEY=<private key PEM>
```

`SGDEV_VPS_PASSWORD` existe como fallback para Terraform, pero es mejor usar
SSH key. No guardes la password del VPS en archivos.

## Primer uso local en Windows

```powershell
cd C:\Users\CFOTech\Documents\Sgdev-infra
Copy-Item terraform\terraform.tfvars.example terraform\terraform.tfvars
notepad terraform\terraform.tfvars
$env:TF_VAR_ssh_private_key = Get-Content $env:USERPROFILE\.ssh\sgdev_deploy -Raw
.\scripts\terraform.ps1 plan -var-file=terraform.tfvars
.\scripts\terraform.ps1 apply -var-file=terraform.tfvars
```

## Primer uso local en Linux/macOS

```bash
cd ~/Documents/Sgdev-infra
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
nano terraform/terraform.tfvars
export TF_VAR_ssh_private_key="$(cat ~/.ssh/sgdev_deploy)"
./scripts/terraform.sh plan -var-file=terraform.tfvars
./scripts/terraform.sh apply -var-file=terraform.tfvars
```

## Publicar portfolio en /portfolio

El portfolio debe compilarse con:

```bash
VITE_BASE_PATH=/portfolio/ docker compose up -d --build
```

La config que Terraform genera para el gateway usa:

```text
APP_SLUG=portfolio
APP_PATH=/portfolio
APP_UPSTREAM=http://portfolio-nginx:80
STRIP_PREFIX=false
```

Con eso el gateway recibe `https://sgdev.com.ar/portfolio/...` y la app conserva
el prefijo `/portfolio`.

## HTTPS

HTTPS se instala con:

```bash
sudo ./scripts/install-https.sh sebasdeveloperlife@gmail.com sgdev.com.ar www.sgdev.com.ar
```

El script usa Let's Encrypt, escribe `proxy/nginx/conf.d/ssl.conf` como archivo
generado local y deja renovacion automatica por cron.

## Pendiente para automatizar desde GitHub

La VPS ya tiene la SSH key de deploy instalada. Para ejecutar Terraform y deploys
desde GitHub Actions falta cargar `SGDEV_SSH_PRIVATE_KEY` en
`Settings > Secrets and variables > Actions`. Los demas valores tienen defaults,
pero conviene cargarlos tambien para que quede explicito.

Si en el futuro mantenes path routing (`/portfolio`, `/egregorai`), cada proyecto
puede tener su propio archivo `/etc/sgdev-infra/apps/<slug>.env` y su propia base
PostgreSQL. Si preferis subdominios, el gateway necesitara un template por host.
