# Shared PostgreSQL pgvector

PostgreSQL compartido para servicios internos de la VPS. No publica puertos al
host ni a internet; otros contenedores lo consumen por la red Docker
`sgdev-data` usando el alias `sgdev-postgres`.

## Instalacion

```bash
sudo cp /opt/sgdev-infra/services/shared-db/.env.example /etc/sgdev-infra/shared-db.env
sudo nano /etc/sgdev-infra/shared-db.env
cd /opt/sgdev-infra
./scripts/shared-db-up.sh
```

El primer arranque crea estas bases con `vector` y `pgcrypto` habilitados:

- `argenticommerce`
- `mercadolibre`
- `rag`

Las apps no deben usar `ports` para acceder a esta base. Deben conectarse a
`sgdev-data` y usar `sgdev-postgres:5432`.
