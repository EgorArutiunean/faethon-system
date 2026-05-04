.PHONY: dev backend frontend db migrate seed test smoke

dev:
	docker compose up --build

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

db:
	docker compose up -d postgres

migrate:
	docker compose run --rm backend alembic upgrade head

seed:
	docker compose run --rm backend python scripts/seed_demo.py

test:
	cd backend && pytest

smoke:
	docker compose ps
