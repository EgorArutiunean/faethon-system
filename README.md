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
  docs/                    Legacy notes and project documentation
  docker-compose.yml
  .env.example
  Makefile
```

## Start With Docker

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
make migrate   # docker compose run backend alembic upgrade head
make seed      # docker compose run backend seed_demo.py
make test      # backend tests
make smoke     # docker compose ps
```

## Publication Status

Current target:

- publish this codebase to GitHub `main`;
- keep production credentials, local databases, logs, build output, downloaded Firebird tools, and legacy working copies out of version control;
- prepare for a future Docker Compose production deployment after server access and production secrets are available.

Verification on 2026-06-16:

- backend tests: `80 passed`;
- backend compileall: successful;
- frontend TypeScript check: successful;
- frontend production build: successful.

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
- PDF print generation;
- advanced report builder;
- full legacy data import.

Those depend on legacy discovery and must be implemented only after the legacy behavior is confirmed. Production launch is gated on a verified data migration plan; see `docs/legacy-data-readiness.md`.

See also: `docs/development-setup.md`.
