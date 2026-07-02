# VPS Google Cloud

## Maquina recomendada

Para probar JanoAI completo junto con otros proyectos:

- Ubuntu 24.04 LTS.
- Compute Engine.
- `e2-medium` si queres margen.
- `e2-small` si queres ahorrar y aceptas builds lentos.
- Disco Persistent Disk Standard de 30 GB como minimo.
- IP externa estatica.
- Firewall: `22`, `80`, `443`.
- No abrir `5432`, `6379`, `3000`, `8080`, `8787` ni `5173`.

`e2-micro` no es recomendable para JanoAI completo porque Java, Next.js,
PostgreSQL, Redis y builds Docker consumen memoria.

## Crear la VM

En Google Cloud Console:

1. Crear o elegir proyecto.
2. Habilitar Compute Engine.
3. Reservar IP estatica regional.
4. Crear VM Ubuntu 24.04 LTS.
5. Elegir `e2-small` o `e2-medium`.
6. Disco standard de 30 GB o mas.
7. Marcar permitir HTTP y HTTPS.
8. Entrar por SSH.

## Instalar host

En la VM:

```bash
sudo apt-get update
sudo apt-get install -y git
sudo git clone URL_DE_ESTE_REPO /opt/sgdev-infra
cd /opt/sgdev-infra
sudo chmod +x scripts/*.sh
sudo ./scripts/install-host.sh
```

Cerrar y volver a abrir SSH si el usuario fue agregado a `docker`.

```bash
cd /opt/sgdev-infra
./scripts/proxy-up.sh
curl http://127.0.0.1/health
```

## Swap para VM chica

En `e2-small`, crear 2 GB de swap ayuda a evitar fallos por memoria durante
builds:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## Checklist de costos

- Una sola VM.
- Sin Cloud SQL al principio.
- Sin GKE.
- Sin Load Balancer.
- Sin Artifact Registry.
- Sin NAT Gateway.
- Sin snapshots automaticas hasta que lo decidas.
- Apagar la VM cuando no la uses para demos largas.
- Crear alerta de presupuesto en Billing.

