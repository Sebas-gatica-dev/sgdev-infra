# Termius y SSH

## Objetivo

Entrar a la VPS desde Termius con clave SSH, operar carpetas y ejecutar comandos
manuales sin copiar secretos en chats.

## Configuracion recomendada

En Google Cloud podes usar el usuario Linux generado por Google o crear uno
claro, por ejemplo `sebas`.

En Termius:

- Host: IP publica estatica de la VM.
- Port: `22`.
- Username: usuario Linux.
- Authentication: SSH key.
- No usar password si podes evitarlo.

No pegues claves privadas en issues, chats ni repos. La clave privada queda en
tu maquina o en el keychain de Termius.

## Carpetas frecuentes

```bash
cd /opt/sgdev-infra
cd /opt/apps/janoai/repo
cd /opt/apps/egregorai/repo
cd /opt/apps/portfolio/repo
```

## Comandos utiles

```bash
# Ver proxy y apps registradas
cd /opt/sgdev-infra
./scripts/app-status.sh

# Logs de una app
./scripts/app-logs.sh janoai

# Entrar al repo de un proyecto
cd /opt/apps/janoai/repo
git status
docker compose ps
```

## SFTP

Termius puede abrir SFTP para revisar archivos. Usalo para inspeccionar o subir
archivos no sensibles. Para `.env`, preferi editar directo en la VM:

```bash
sudo nano /etc/sgdev-infra/apps/janoai.env
nano /opt/apps/janoai/repo/.env.production
```
