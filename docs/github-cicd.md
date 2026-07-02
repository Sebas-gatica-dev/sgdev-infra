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
