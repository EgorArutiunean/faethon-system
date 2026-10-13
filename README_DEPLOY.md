# Buy Modern Deployment

This guide describes deployment on a real server with Docker Compose and PostgreSQL.

Do not commit real production credentials. Use `.env.production.example` as a template only.

## Current Deployment Decision

As of 2026-10-12 the project is suitable for demo/UAT, but remains **NO-GO for
production**. The authoritative release gate and current evidence are maintained
in `docs/deployment-work-plan.md`.

A live production deployment remains blocked until the release candidate is
committed and verified, production infrastructure and secrets are available,
the approved opening data set is reconciled, and restore/UAT rehearsals pass.

Before a production server launch, complete `docs/legacy-data-readiness.md` and rerun the production smoke checklist below.

## Requirements

- Linux server or Windows server with Docker Desktop / Docker Engine.
- Docker Compose v2.
- Open inbound HTTP port, default `80`.
- Enough disk space for PostgreSQL data and backups.
- Production values for PostgreSQL credentials, `AUTH_SECRET_KEY`, public origin, and backup retention.

Real release deployment uses `docker-compose.release.yml`, which accepts only
prebuilt backend/frontend images. The release workflow validates immutable
GHCR digests and never runs `docker compose build` on the target host.

## First Deploy

1. Copy production env template:

```bash
cp .env.production.example .env.production
```

2. Edit `.env.production`:

- set a strong `POSTGRES_PASSWORD`;
- set a long random `AUTH_SECRET_KEY`;
- set `CORS_ORIGINS` to the public origin;
- review `LOGIN_MAX_ATTEMPTS` and `LOGIN_LOCK_MINUTES` (defaults: 5 attempts / 15 minutes);
- keep `ACCESS_TOKEN_MINUTES` at 60 or lower in production;
- keep nginx `client_max_body_size` aligned with `IMPORT_MAX_BYTES` (default 10 MiB);
- set `HTTP_PORT` if not using port 80.

Terminate TLS at the host reverse proxy/load balancer or extend this nginx
container with the approved certificate automation. Public production access
must be HTTPS-only and redirect HTTP to HTTPS. The application nginx emits HSTS,
CSP, frame, MIME-sniffing, referrer, permissions and opener policies; validate
them through the final public URL after TLS termination. Do not add HSTS preload
until every required subdomain is permanently HTTPS-capable.

3. For local infrastructure validation only, build the production images:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml build
```

4. Start the local validation stack. The one-shot `migrate` service runs before
   backend and blocks application startup if Alembic fails:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --wait
```

5. Create the first administrator once. Supply the bootstrap values through the
   deployment platform's temporary secret mechanism; do not save the bootstrap
   password in `.env.production`, shell history, or Git:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm \
  -e BOOTSTRAP_ADMIN_EMAIL -e BOOTSTRAP_ADMIN_PASSWORD -e BOOTSTRAP_ADMIN_FULL_NAME \
  backend python scripts/bootstrap_admin.py
```

The bootstrap command refuses to reset an existing account. `seed_demo.py` and
the known demo credentials are disabled when `APP_ENV=production`. The first
login is restricted to the password-change screen until the bootstrap password
is replaced with a personal password of at least 12 characters.

Failed login state is persisted in PostgreSQL. Five consecutive invalid
passwords lock the account for 15 minutes by default; successful login,
self-service password change, or an administrator password reset clears the
counter. Login responses remain generic and do not disclose password validity.

The first release uses access-only JWTs with no refresh token. Production TTL
is limited to 60 minutes. Logout, self-service password change, and an
administrator password reset increment the user's token version and immediately
revoke every previously issued token for that account.

Imports accept only UTF-8 CSV and XLSX. Backend defaults limit uploads to 10 MiB
and 20,000 data rows. XLSX archives are rejected before parsing when entry count,
expanded size, encryption, or compression ratio exceeds the configured safety
limits. Increasing nginx or backend limits requires a matching load/security test.

6. Check readiness:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl http://localhost/health/ready
```

7. Run the manual smoke scenarios listed under Update Procedure.

## Historical Smoke Evidence

The Docker/PostgreSQL stack was smoke-tested successfully on 2026-05-03. This
is historical evidence only and does not qualify the current release candidate.

Confirmed:

- Docker/PostgreSQL startup succeeded.
- Containers reached healthy/running state.
- Frontend opened through nginx.
- The then-current demo administrator login worked.

See `docs/deployment-smoke.md` for the historical commands and resolved issues.
Before release, repeat the smoke against the exact immutable image digest and
record the result in `docs/deployment-work-plan.md`.

## Migrations

Migrations run as the separate one-shot `migrate` service:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm migrate
```

This avoids hidden schema changes during container restart.

## Backup

Linux/macOS:

```bash
ENV_FILE=.env.production COMPOSE_FILE=docker-compose.prod.yml scripts/backup_postgres.sh
```

PowerShell:

```powershell
.\scripts\backup_postgres.ps1 -EnvFile .env.production -ComposeFile docker-compose.prod.yml
```

Backups are written atomically to the ignored local `backups/` directory as
custom-format PostgreSQL dumps. Each dump is validated with `pg_restore --list`
and receives a SHA-256 sidecar file. Default retention is 14 days and only exact
`buy_modern_*.dump`/checksum names are eligible; set `BACKUP_RETENTION_DAYS=0`
to disable deletion.

On the production Linux host use the hourly systemd templates under
`ops/systemd/`. Set `BACKUP_COMPOSE_PROJECT=buy-modern-production` so the job
finds PostgreSQL through Docker labels without reading the deployment secret
env-file. Detailed installation and alert checks are in
`docs/backup-operations.md`.

Production backup scheduling also runs `scripts/offsite_backup.sh` after the
local dump. It requires a pre-created Restic repository and password file;
configuration, encryption-key custody, object lock and restore verification are
documented in `docs/backup-operations.md`.

## Restore

Restoring replaces database objects in the target database. Take a fresh backup first.

Linux/macOS:

```bash
ENV_FILE=.env.production COMPOSE_FILE=docker-compose.prod.yml scripts/restore_postgres.sh backups/buy_modern_YYYYMMDD-HHMMSS.dump
```

PowerShell:

```powershell
.\scripts\restore_postgres.ps1 -BackupFile .\backups\buy_modern_YYYYMMDD-HHMMSS.dump -EnvFile .env.production -ComposeFile docker-compose.prod.yml
```

## Update Procedure

1. Take a backup.
2. Obtain the approved backend/frontend `image@sha256:...` references from the
   release manifest. Never rebuild on the server.
3. Pull the exact images with `docker-compose.release.yml`:

```bash
BACKEND_IMAGE=ghcr.io/example/backend@sha256:... \
FRONTEND_IMAGE=ghcr.io/example/frontend@sha256:... \
RELEASE_VERSION=vX.Y.Z-rc.N \
docker compose --env-file .env.production -f docker-compose.release.yml pull
```

4. Deploy; Compose runs migration before backend and waits for health:

```bash
BACKEND_IMAGE=ghcr.io/example/backend@sha256:... \
FRONTEND_IMAGE=ghcr.io/example/frontend@sha256:... \
RELEASE_VERSION=vX.Y.Z-rc.N \
docker compose --env-file .env.production -f docker-compose.release.yml up -d --wait
```

5. Smoke test login, documents, stock, payments, cash, reports, export, print, and import dry-run.

6. Verify migrated legacy totals against `docs/legacy-data-readiness.md`.

## Rollback Basics

Use the manual **Roll back production application** GitHub Actions workflow.
It requires production Environment approval, the previous backend/frontend
digest references, failed deployment reference and incident/change ticket.

The workflow first verifies that the target backend Alembic head equals the
current database revision. A mismatch blocks application rollback: do not force
it and do not run `alembic downgrade`; choose a forward fix or the separately
approved restore procedure.

Manual application-only fallback uses the previous approved manifest and
`--no-deps`, so the migration service is not started:

```bash
BACKEND_IMAGE=ghcr.io/example/backend@sha256:previous... \
FRONTEND_IMAGE=ghcr.io/example/frontend@sha256:previous... \
RELEASE_VERSION=vPREVIOUS \
docker compose --env-file .env.production -f docker-compose.release.yml \
  up -d --no-deps --wait backend frontend
```

After rollback, repeat readiness/login/business smoke and record the rollback
manifest. Do not run automatic Alembic downgrade. Restore a database backup only
under the approved incident/restore procedure if an incompatible migration
changed data; a normal application rollback assumes backward-compatible migrations.

There is no automated schema downgrade policy yet.

## Troubleshooting

- Backend unhealthy: check `DATABASE_URL`, `AUTH_SECRET_KEY`, and PostgreSQL health.
- Frontend opens but API fails: verify nginx `/api` proxy and backend service health.
- Login fails after restart: verify the same `AUTH_SECRET_KEY` is used across backend restarts.
- Import upload fails: check nginx `client_max_body_size` in `frontend/nginx.conf`.
- Database connection refused: wait for Postgres healthcheck or inspect `postgres` logs.
- Docker unavailable: install Docker Compose v2; this repository cannot validate production compose without Docker.
