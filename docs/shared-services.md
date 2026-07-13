# Servicios compartidos SGDEV

Esta infra ahora separa tres redes Docker:

- `sgdev-proxy`: trafico HTTP/HTTPS hacia apps publicas.
- `sgdev-data`: datos compartidos, especialmente `sgdev-postgres`.
- `sgdev-services`: APIs internas compartidas entre apps.

## PostgreSQL pgvector compartido

El servicio vive en `services/shared-db` y no publica puertos. Otros
contenedores acceden por:

```text
sgdev-postgres:5432
```

Arranque:

```bash
cd /opt/sgdev-infra
sudo cp services/shared-db/.env.example /etc/sgdev-infra/shared-db.env
sudo nano /etc/sgdev-infra/shared-db.env
./scripts/shared-db-up.sh
```

El primer arranque crea bases `argenticommerce`, `mercadolibre` y `rag`, todas
con `vector` y `pgcrypto`.

## MercadoLibre / MercadoPago API

El microservicio vive en `services/mercadolibre` y expone internamente:

```text
http://mercadolibre-api:8080
```

Endpoints privados requieren:

```text
X-SGDEV-Service-Token: <SERVICE_TOKEN>
```

Rutas principales:

- `POST /v1/payments/checkout/preferences`
- `POST /v1/payments/subscription-plans`
- `POST /v1/payments/subscriptions`
- `GET /v1/mercadolibre/oauth/authorize-url`
- `POST /v1/mercadolibre/oauth/exchange`
- `POST /webhooks/mercadopago`

Registro recomendado:

```bash
cd /opt/sgdev-infra
sudo cp services/mercadolibre/.env.example /etc/sgdev-infra/mercadolibre.env
sudo nano /etc/sgdev-infra/mercadolibre.env
sudo cp examples/apps/mercadolibre.env.example /etc/sgdev-infra/apps/mercadolibre.env
./scripts/app-deploy.sh mercadolibre --no-pull
```

## ArgentiCommerce

La app debe registrarse con `STRIP_PREFIX=false`:

```bash
sudo cp examples/apps/argenticommerce.env.example /etc/sgdev-infra/apps/argenticommerce.env
./scripts/app-deploy.sh argenticommerce
```

El repo de ArgentiCommerce debe tener `.env.sgdev` basado en
`DEPLOY_SGDEV.md` y `compose.sgdev.yml`.
