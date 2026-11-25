.PHONY: dev backend frontend db migrate seed test smoke legacy

ifeq ($(OS),Windows_NT)
LEGACY_UID ?= 65534
LEGACY_GID ?= 65534
else
LEGACY_UID ?= $(shell id -u)
LEGACY_GID ?= $(shell id -g)
endif
export LEGACY_UID LEGACY_GID

dev:
	docker compose up --build

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

db:
	docker compose up -d postgres

legacy:
ifeq ($(OS),Windows_NT)
	docker compose --profile legacy up -d --build legacy
else
	@if [ "$(LEGACY_UID)" = "0" ]; then \
		echo "make legacy must run as the owner of the read-only copy, not as root" >&2; \
		exit 1; \
	fi
	docker compose --profile legacy up -d --build legacy
endif

migrate:
	docker compose run --rm backend alembic upgrade head

seed:
	docker compose run --rm backend python scripts/seed_demo.py

test:
	cd backend && pytest

smoke:
	docker compose ps
