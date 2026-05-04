# Development Setup

The target development environment uses PostgreSQL through Docker Compose.

Legacy discovery remains separate under `migration/legacy_discovery` and is not part of this setup.

## Prerequisites

- Docker Desktop with Docker Compose v2.
- Node.js only if running the frontend outside Docker.
- Python only if running backend tests outside Docker.

On 2026-05-02 this machine could not run Docker validation because `docker` was not found in `PATH`.

## Environment

Create `.env` from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Important variables:

- `DATABASE_URL=postgresql+psycopg://buy:buy@postgres:5432/buy_modern`
- `JWT_SECRET_KEY` / `AUTH_SECRET_KEY`
- `ACCESS_TOKEN_MINUTES`
- `VITE_API_BASE_URL=/api/v1`
- `VITE_API_PROXY_TARGET=http://backend:8000`

The application accepts both `JWT_SECRET_KEY` and `AUTH_SECRET_KEY`; `AUTH_SECRET_KEY` is the internal backend setting name.

## Docker Workflow

Start PostgreSQL:

```powershell
make db
```

Apply migrations:

```powershell
make migrate
```

Seed demo data and demo users:

```powershell
make seed
```

Start all services:

```powershell
make dev
```

Open:

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/health`
- OpenAPI: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

Demo login:

- `admin@example.com / admin123`
- `manager@example.com / manager123`
- `cashier@example.com / cashier123`
- `viewer@example.com / viewer123`

## Smoke Checklist

After `make dev`, verify:

- backend `/health` returns `200`;
- frontend login works as `admin@example.com / admin123`;
- Products opens;
- Documents opens;
- Stock opens;
- Payments opens;
- Cash opens;
- Reports opens;
- document Print opens a browser print view;
- Reports Export XLSX downloads;
- Reports Export CSV downloads.

## Local SQLite Fallback

SQLite fallback is temporary and only for local development when Docker/PostgreSQL is unavailable:

```powershell
cd backend
$env:DATABASE_URL='sqlite:///./buy_modern_dev.db'
python -c "from app.db.session import Base, engine; import app.db.base; Base.metadata.create_all(engine)"
python scripts/seed_demo.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

PostgreSQL remains the target database for reproducible development.
