# Deployment Smoke

Date: 2026-05-03

## Result

Production Docker/PostgreSQL launch completed successfully.

Confirmed:

- Docker Compose production stack started successfully.
- PostgreSQL started successfully.
- All containers reached healthy/running state.
- Frontend opened successfully through nginx.
- Admin login works with `admin@example.com / admin123`.

## Commands Used

Production environment file was prepared from `.env.production` with:

```env
POSTGRES_USER=buy_user
POSTGRES_PASSWORD=buy_password_123
POSTGRES_DB=buy_modern
AUTH_SECRET_KEY=super_secret_key_123456
ACCESS_TOKEN_MINUTES=1440
```

Deployment commands:

```powershell
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend python scripts/seed_demo.py
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Smoke checks:

```powershell
Invoke-WebRequest http://localhost/health
```

Browser checks:

- Opened frontend at `http://localhost`.
- Logged in as `admin@example.com / admin123`.

## Problems And Resolutions

### Production Env Missing Real Values

Problem: `.env.production` initially contained placeholder values from the example file.

Resolution: updated `.env.production` with minimum deployment values and synchronized `DATABASE_URL` with the configured PostgreSQL user/password:

```env
DATABASE_URL=postgresql+psycopg://buy_user:buy_password_123@postgres:5432/buy_modern
```

### Previous Local Docker Blocker

Problem: earlier local validation was blocked because Docker CLI was not available in `PATH`.

Resolution: deployment smoke was performed after Docker/PostgreSQL became available on the target machine/environment.

## Follow-Up

- Replace demo credentials before real production use.
- Replace `AUTH_SECRET_KEY` and database password with strong deployment secrets.
- Take a PostgreSQL backup after confirming production data.
- Keep `.env.production` out of version control.
