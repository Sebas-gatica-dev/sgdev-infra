# Terraform y GitHub Actions

Este repo puede administrar el gateway `sgdev.com.ar` en la VPS `143.95.217.87`.

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
SGDEV_INFRA_REPO_URL=git@github.com:OWNER/Sgdev-infra.git
SGDEV_PORTFOLIO_REPO_URL=git@github.com:OWNER/sg-ai-agent-portfolio.git
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
APP_UPSTREAM=http://host.docker.internal:18080
STRIP_PREFIX=false
```

Con eso el gateway recibe `https://sgdev.com.ar/portfolio/...` y la app conserva
el prefijo `/portfolio`.

## Datos que faltan para automatizar al 100%

- URL final del repo GitHub de `Sgdev-infra`.
- URL final del repo GitHub del portfolio.
- SSH key de deploy instalada en la VPS y en GitHub Secrets.
- Email para Let's Encrypt si queres activar HTTPS automático.
- Confirmar si vas a mantener path routing (`/portfolio`, `/egregorai`) o pasar
  a subdominios más adelante.
