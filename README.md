# Faethon System / Buy Modern

Modern replacement scaffold for the legacy BuySell accounting/warehouse application.

Legacy discovery continues under `migration/legacy_discovery`. The new app does not mechanically copy the old InterBase schema; business rules that still need confirmation are marked with `TODO LEGACY_RULE_REQUIRED`.

This repository is intended to be published as `EgorArutiunean/faethon-system`. The current codebase is the working `buy-modern` MVP that replaces the earlier Vite/MUI prototype in that GitHub repository.

## Stack

- Backend: FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic.
- Database: PostgreSQL.
- Frontend: React, TypeScript, Vite, Tailwind CSS.
- Infra: Docker Compose.

## Structure

```text
buy-modern/
  backend/                 FastAPI app, SQLAlchemy models, Alembic, tests
  frontend/                React + TypeScript + Vite working UI
  migration/               Legacy discovery and future ETL workspace
  tools/interbase/         Read-only browser for the InterBase BUY.GDB copy
  docs/                    Legacy notes and project documentation
  docker-compose.yml
  .env.example
  Makefile
```

## Start With Docker

For staging/production on an existing Coolify server, follow
[the Coolify deployment guide](docs/coolify-deployment.md). Use
`docker-compose.coolify.yml` and `.env.coolify.example` with published image
digests. The development instructions below create demo accounts and are not
the Coolify deployment procedure.

```powershell
Copy-Item .env.example .env
make db
make migrate
make seed
make dev
```

Services:

- Frontend: `http://localhost:5173`
- Backend OpenAPI: `http://localhost:8000/docs`
- Healthcheck: `http://localhost:8000/health`
- PostgreSQL: `localhost:5432`

## Legacy database

`miscelanious/BUY.GDB` is an InterBase 7.1 file (ODS 11.1). Firebird cannot open it, and the bundled `gbak.exe` / `gfix.exe` are older than the file. Do not run `FUNSTART.BAT`.

The `legacy` Compose service reads a read-only copy and serves a small browser plus a JSON API. It is not part of `make dev`. Docker is the only install step.

```bash
mkdir -p migration/legacy_work
cp miscelanious/BUY.GDB migration/legacy_work/BUY_COPY.GDB
chmod a-w migration/legacy_work/BUY_COPY.GDB
make legacy
```

`migration/legacy_work/` is gitignored. The service mounts `BUY_COPY.GDB` read-only and restarts with Docker.

- Browser: `http://127.0.0.1:8765`
- From another container: `http://legacy:8765`
- Tables: `GET /api/tables`
- Rows: `GET /api/rows?table=SGRP&limit=50&offset=0&q=`

Text is Windows-1251. `LICO` contains personal data. This is a page reader, not a SQL server. Stop it with `docker compose --profile legacy stop legacy`.

Run migrations:

```powershell
make migrate
```

Seed demo data:

```powershell
make seed
```

Demo users:

- `admin@example.com / admin123`
- `manager@example.com / manager123`
- `cashier@example.com / cashier123`
- `logist@example.com / logist123`
- `viewer@example.com / viewer123`

## Local Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## Local Frontend

```powershell
cd frontend
npm install
npm run dev
```

## Make Targets

```powershell
make dev       # docker compose up --build
make backend   # local uvicorn
make frontend  # local vite
make db        # postgres only, detached
make legacy    # read-only InterBase browser at http://127.0.0.1:8765
make migrate   # docker compose run backend alembic upgrade head
make seed      # docker compose run backend seed_demo.py
make test      # backend tests
make smoke     # docker compose ps
```

## Manager Workflow Tests

Deterministic frontend workflow tests:

```powershell
cd frontend
npm run test:e2e
```

Real incoming, sale, insufficient-stock, transfer, customer-payment, and
supplier-payment workflows against an isolated PostgreSQL database:

```powershell
cd frontend
npm run test:e2e:real
```

The real E2E command uses `docker-compose.e2e.yml`, applies migrations, runs the
browser scenario, and removes the temporary containers and data after the run.
It does not modify the regular development database.

## Publication Status

Current target:

- publish this codebase to GitHub `main`;
- keep production credentials, local databases, logs, build output, downloaded Firebird tools, and legacy working copies out of version control;
- prepare for a future Docker Compose production deployment after server access and production secrets are available.

Verification on 2026-09-01:

- backend tests: `123 passed` using the local SQLite test configuration;
- frontend TypeScript check: successful;
- frontend production build: successful.
- frontend mock Playwright: `3 passed`;

PostgreSQL real E2E was not repeated on 2026-09-01 because Docker Desktop was
not running. The latest recorded successful PostgreSQL result is `7 passed` on
2026-07-24.

## Current Scope

Implemented:

- health endpoint;
- auth with demo roles and permissions;
- products, partners, warehouses, documents, stock, payments, cash;
- reports, XLSX/CSV export, and HTML document print form;
- Alembic migrations;
- React operational UI for daily operator workflows.

Not implemented yet:

- final legacy-compatible accounting behavior;
- logistics task execution and confirmations;
- advanced report builder;
- full legacy data import.

Those depend on legacy discovery and must be implemented only after the legacy behavior is confirmed. Production launch is gated on a verified data migration plan; see `docs/legacy-data-readiness.md`.

See also: `docs/development-setup.md`.
