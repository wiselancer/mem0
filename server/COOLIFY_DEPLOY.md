# Deploy Mem0 on Coolify

Use this fork as the deployment source in Coolify.

## Application

Create a new Docker Compose application:

- Repository: `https://github.com/wiselancer/mem0`
- Branch: your pinned deployment branch
- Base directory: `server`
- Compose file: `docker-compose.yaml`

For local development, use `docker-compose.dev.yaml`.

## Domains

Assign domains to these services:

- `mem0-dashboard`, port `3000`: `https://mem0.yourdomain.com`
- `mem0`, port `8000`: `https://mem0-api.yourdomain.com`

Postgres must not have a domain and must not expose a host port.

## Environment Variables

Add these in Coolify:

```env
OPENAI_API_KEY=...
POSTGRES_PASSWORD=...
JWT_SECRET=...
DASHBOARD_URL=https://mem0.yourdomain.com
API_URL=https://mem0-api.yourdomain.com
ADMIN_API_KEY=
MEM0_TELEMETRY=false
```

Generate secrets with:

```bash
openssl rand -base64 48
```

## First Run

After deploy, open the dashboard URL. Mem0 will route a fresh install to the setup wizard, where you create the first admin and generate an API key.

Use that API key from clients:

```python
from mem0 import MemoryClient

client = MemoryClient(
    api_key="m0sk_...",
    host="https://mem0-api.yourdomain.com",
)
```

## Operations

- Keep `AUTH_DISABLED=false` in production.
- Back up the `postgres_db` volume or run scheduled `pg_dump` backups.
- Deploy from a pinned branch/tag, not directly from upstream `main`.
- Recreate containers after environment changes so Docker Compose reloads env values.
