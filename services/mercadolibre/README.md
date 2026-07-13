# MercadoLibre / MercadoPago microservice

API interna para centralizar integraciones de MercadoLibre y MercadoPago dentro
de la infraestructura SGDEV.

## Capacidades

- OAuth server-side de MercadoLibre.
- Checkout Pro via preferencias de Mercado Pago.
- Planes y suscripciones via `preapproval_plan` y `preapproval`.
- Webhook publico para Mercado Pago.
- Persistencia en PostgreSQL compartido (`sgdev-postgres`) sobre `sgdev-data`.
- Token de servicio (`SERVICE_TOKEN`) para que solo otras apps internas llamen
  endpoints privados.

## Despliegue

1. Levantar primero la DB compartida.
2. Crear secretos:

```bash
sudo cp /opt/sgdev-infra/services/mercadolibre/.env.example /etc/sgdev-infra/mercadolibre.env
sudo nano /etc/sgdev-infra/mercadolibre.env
```

3. Registrar como app publica para recibir webhooks:

```bash
cd /opt/sgdev-infra
sudo APP_ID=mercadolibre COMPOSE_FILES="services/mercadolibre/compose.yml" ENV_FILE=/etc/sgdev-infra/mercadolibre.env \
  ./scripts/app-new.sh mercadolibre /opt/sgdev-infra http://mercadolibre-api:8080 /mercadolibre services/mercadolibre/compose.yml /etc/sgdev-infra/mercadolibre.env
./scripts/app-deploy.sh mercadolibre --no-pull
```

Servicios internos deben llamar a:

```text
http://mercadolibre-api:8080
```

con header:

```text
X-SGDEV-Service-Token: <SERVICE_TOKEN>
```
