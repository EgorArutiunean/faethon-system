# Buy Modern Deployment

This guide describes deployment on a real server with Docker Compose and PostgreSQL.

Do not commit real production credentials. Use `.env.production.example` as a template only.

## Requirements

- Linux server or Windows server with Docker Desktop / Docker Engine.
- Docker Compose v2.
- Open inbound HTTP port, default `80`.
- Enough disk space for PostgreSQL data and backups.

## First Deploy

1. Copy production env template:

```bash
cp .env.production.example .env.production
```

2. Edit `.env.production`:

- set a strong `POSTGRES_PASSWORD`;
- set a long random `AUTH_SECRET_KEY`;
- set `CORS_ORIGINS` to the public origin;
- set `HTTP_PORT` if not using port 80.

3. Build and start services:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

4. Run migrations:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

5. Seed demo/admin users only when appropriate:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend python scripts/seed_demo.py
```

The demo users are for controlled deployments and should be changed or disabled before real production use.

6. Check health:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl http://localhost/health
```

## Verified Smoke

The production Docker/PostgreSQL stack was smoke-tested successfully on 2026-05-03.

Confirmed:

- Docker/PostgreSQL startup succeeded.
- Containers reached healthy/running state.
- Frontend opened through nginx.
- Admin login worked with `admin@example.com / admin123`.

See `docs/deployment-smoke.md` for commands used and resolved issues.

## Migrations

Migrations are intentionally run as a separate command before or during deployment:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

This avoids hidden schema changes during container restart.

## Backup

Linux/macOS:

```bash
COMPOSE_FILE=docker-compose.prod.yml scripts/backup_postgres.sh
```

PowerShell:

```powershell
.\scripts\backup_postgres.ps1 -ComposeFile docker-compose.prod.yml
```

Backups are written to the local `backups/` directory as custom-format PostgreSQL dumps.

## Restore

Restoring replaces database objects in the target database. Take a fresh backup first.

Linux/macOS:

```bash
COMPOSE_FILE=docker-compose.prod.yml scripts/restore_postgres.sh backups/buy_modern_YYYYMMDD-HHMMSS.dump
```

PowerShell:

```powershell
.\scripts\restore_postgres.ps1 -BackupFile .\backups\buy_modern_YYYYMMDD-HHMMSS.dump -ComposeFile docker-compose.prod.yml
```

## Update Procedure

1. Take a backup.
2. Pull or copy the new release.
3. Rebuild images:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml build
```

4. Run migrations:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

5. Restart:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

6. Smoke test login, documents, stock, payments, cash, reports, export, print, and import dry-run.

## Rollback Basics

1. Stop services:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml down
```

2. Restore the previous app release.
3. Restore database backup if the failed release ran migrations or changed data.
4. Start services again.

There is no automated schema downgrade policy yet.

## Troubleshooting

- Backend unhealthy: check `DATABASE_URL`, `AUTH_SECRET_KEY`, and PostgreSQL health.
- Frontend opens but API fails: verify nginx `/api` proxy and backend service health.
- Login fails after restart: verify the same `AUTH_SECRET_KEY` is used across backend restarts.
- Import upload fails: check nginx `client_max_body_size` in `frontend/nginx.conf`.
- Database connection refused: wait for Postgres healthcheck or inspect `postgres` logs.
- Docker unavailable: install Docker Compose v2; this repository cannot validate production compose without Docker.
