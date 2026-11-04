# Agent instructions

Buy Modern (`faethon-system` on `main`) is the PostgreSQL replacement for the legacy BuySell warehouse and accounting program. The running app is FastAPI, SQLAlchemy 2, Alembic, React, TypeScript, and Vite. PostgreSQL 16 is the application database. SQLite exists only for unit tests and a temporary local fallback.

Read the service and its tests before changing a business rule. Several files under `docs/` describe an earlier slice and disagree with the code. When they disagree, the service and the tests win.

## Spend fewer tokens

Use graft and [RTK](https://github.com/rtk-ai/rtk) before you read whole files or raw command logs. Both are local CLIs. If one is not installed, use the normal command. Do not add either tool as a project dependency.

graft answers questions about this repo from `graft/`, which is gitignored. If `graft map` reports no graph, run `graft build` once.

| Need | Command |
| --- | --- |
| Where the code lives | `graft map` |
| How a behavior works | `graft ask "<question>" --source` |
| A file's API | `graft skeleton <path>` |
| Every use of a name | `graft grep "<symbol>"` |
| What breaks if a symbol changes | `graft callers <symbol> --depth 2` |

Do not pipe graft through `head`, `tail`, or `sed`. Open a source file only when the returned span is truncated or too small to edit from.

RTK compresses shell output. Prefer it for the noisy commands in this repo:

- `rtk pytest`, `rtk ruff check`, and `rtk mypy` in `backend/`
- `rtk tsc` and `rtk playwright test` in `frontend/`
- `rtk git status`, `rtk git diff`, and `rtk git log`
- `rtk docker` for Compose output

When a filter hides the line you need, recover that output with `rtk recall` instead of reading the full log again.

## Where a change goes

| Change | Edit |
| --- | --- |
| Posting, stock, payments, cash, import, reports | `backend/app/services/` |
| HTTP shape and permission gate | `backend/app/api/routes/` plus `backend/app/schemas/` |
| Tables and constraints | `backend/app/models/` and a new file in `backend/alembic/versions/` |
| Role grants for a fresh seed | `PERMISSIONS` and `ROLE_PERMISSIONS` in `backend/app/services/auth_seed.py` |
| Screen behavior | one page in `frontend/src/pages/`, then `frontend/src/lib/api.ts` |
| Visible copy | both `en` and `ru` in `frontend/src/i18n.tsx` |
| Demo login data | `backend/scripts/seed_demo.py` |
| Legacy InterBase reader | `tools/interbase/` |

Routes stay thin: `require_permission(...)`, then a service call. Mutations that matter call `write_audit`. Amounts are `Decimal` in Python and strings on the API. Do not do accounting arithmetic in a React page.

`docs/domain-model/document-lifecycle.md` still says a posted document is read-only. The code corrects one through `repost_document`. `docs/domain-model/known-simplifications.md` still says payment allocation and user administration are missing. Both exist. Do not reintroduce either limitation from those files.

A comment marked `TODO LEGACY_RULE_REQUIRED` is a stop. Do not invent the BuySell rule, flip a debt sign, or replace the current behavior while passing through that code. Confirmed behavior belongs in the service, with a test that names the rule.

## Accounting rules the code enforces

Documents are `incoming`, `outgoing`, `adjustment`, or `transfer`, and `draft`, `posted`, or `cancelled`.

- Header and line edits, and physical delete, apply to drafts only.
- `post_document` posts a draft, locks the affected stock keys, refuses a result below zero, increments `posting_version`, writes movements and a revision, then creates logistics tasks.
- A posted document changes only through `repost_document`, which keeps the previous revision.
- `cancel_document` reverses the active movements of a posted document. It refuses when the reversal would make stock negative, and when posted payments are still allocated to that document. Reallocate first.
- Incoming requires a `supplier` or `both` partner. Outgoing requires a `customer` or `both` partner. A transfer has two different warehouses and no partner. Adjustment may omit the partner.
- Document numbers are unique. Generated prefixes are `IN-`, `OUT-`, `ADJ-`, and `TR-`.
- Posting a customer payment creates `cash_in`. Posting a supplier payment or a refund creates `cash_out`. Refund cash direction is still marked unconfirmed; do not change it. A manager allocates a posted payment across invoices without a second cash movement.
- A cash `correction` sets the target balance, requires a reason, and stores the difference. The cash ledger is not allowed to go negative. There is one cash desk.
- Latest posted incoming purchase is the current product cost. A sale price below 10% markup over that cost is a warning, not a block.
- Opening stock and opening partner balances from Import Lite are an interim representation. Leave them in place until a confirmed legacy rule replaces them.
- `BUY.GDB` supplies directories and reference data. It is not a source of historical documents, payments, cash entries, or postings.

Partner debt signs in `payments_service` are explicitly unconfirmed. Preserve the current sign convention and its tests.

## Access

Permissions are `object.action` strings checked by `require_permission`. A user with `must_change_password` is rejected with `PASSWORD_CHANGE_REQUIRED`. Access tokens carry `ver`; a mismatch means the token was revoked.

Seeded roles are `admin`, `manager`, `cashier`, `logist`, and `viewer`. `seed_auth_defaults` creates admin, manager, cashier, and viewer. `seed_demo.py` also creates `logist@example.com` and assigns demo warehouses. Demo seeding raises in production. Demo passwords are for local and CI use only.

`seed_permissions_and_roles` rewrites every role's grants from `ROLE_PERMISSIONS`. Alembic `0012` separately removes `logistics.process` and `logistics.review`. Those two sources disagree. Before changing logistics access, read `backend/tests/test_logistics_access.py`, `auth_seed.py`, and that migration together. Logistics visibility is warehouse-scoped on the server. Hiding a price or a row only in React is not sufficient.

A new permission needs the code in `PERMISSIONS`, the role lists, a migration for databases that already ran, and an auth test. Do not grant it by editing only the frontend.

## Legacy database

The modern app is PostgreSQL. `miscelanious/BUY.GDB` is a separate read-only source, not the application database. It is InterBase 7.1, ODS 11.1, page size 4096, dialect 1, Windows-1251. Firebird clients and servers cannot open it. Do not download `fbclient.dll`, do not run `inspect_firebird.py` against this file, and do not install InterBase to browse it.

Do not run `FUNSTART.BAT`, `gfix -mend`, `gfix -sweep`, or `gbak -R`. Do not write to the original file. Work only with `migration/legacy_work/BUY_COPY.GDB`, which is gitignored.

Start the reader:

```bash
mkdir -p migration/legacy_work
cp miscelanious/BUY.GDB migration/legacy_work/BUY_COPY.GDB
chmod a-w migration/legacy_work/BUY_COPY.GDB
make legacy
```

- Browser: `http://127.0.0.1:8765`
- Other containers: `http://legacy:8765`
- `GET /api/tables`
- `GET /api/rows?table=TABLE&limit=50&offset=0&q=`

`make dev` does not start this service. `LICO` contains personal data; do not export it wholesale. CloudBeaver, FlameRobin, and FirebirdWebAdmin need a real InterBase server and cannot attach to this container.

Code lives in `tools/interbase/`. The Compose service name is `legacy`, image `buy-legacy-gdb`, profile `legacy`. `BUY.GDB` supplies directories and reference data. It is not a source of historical documents, payments, cash entries, or postings.

Do not commit `.env*`, `backups/`, `*.dump`, root `*.xls` / `*.xlsx`, `migration/legacy_work/`, `migration/legacy_exports/`, `migration/source_data/`, `release-artifacts/`, or the original files under `miscelanious/` (`BUY.GDB`, `Buysell.exe`, `FUNSTART.BAT`, `gfix.exe`, `gbak.exe`, and the other local binaries).

## Run and verify

From a copy of `.env.example`:

```bash
make db
make migrate
make seed
make dev
```

App: `http://localhost:5173`. API: `http://localhost:8000/docs`. Health: `http://localhost:8000/health`. API prefix: `/api/v1`.

While you are iterating, wrap pytest, ruff, mypy, tsc, Playwright, git, and Docker with RTK. The commands below are what CI runs.

Backend, from `backend/`, with Python 3.12:

```bash
ruff check app scripts tests alembic
ruff format --check app scripts tests alembic
mypy app scripts
python -m pytest -q --cov=app --cov-branch --cov-fail-under=82.5
```

The default test database is in-memory SQLite. Stock locking and migration checks need PostgreSQL. CI runs `tests/test_postgres_concurrency.py` and `tests/test_postgres_accounting_core.py` against Postgres 16, then `alembic check`. Run those when a change touches posting, balances, numbering, or migrations.

Frontend, from `frontend/`, with Node 22:

```bash
npm run typecheck
npm run build
npm run test:e2e
```

`npm run test:e2e` mocks the API. `npm run test:e2e:real` and `npm run test:e2e:prod` start isolated Compose stacks and tear them down. They do not use the development database. Use the real stack when the change crosses the API and a manager workflow: incoming, sale, stock shortage, transfer, or payment allocation.

Ruff line length is 100. Do not add a ticket key to a comment. Say why the code is there.

After a schema change: new Alembic revision, `alembic upgrade head`, and `alembic check`. Do not rely on `Base.metadata.create_all` for PostgreSQL. `seed_demo.py` calls it only so a local SQLite file can boot.

## Deploy and backups

Development Compose is `docker-compose.yml`. Staging and production on Coolify use `docker-compose.coolify.yml` and published image digests. Do not point a Coolify deploy at the development seed flow.

`APP_ENV=production` refuses the demo auth secret, a secret shorter than 32 characters, access tokens over 60 minutes, non-JSON logs, and any CORS origin that is not `https://`. Keep those checks.

Backup and restore behavior is covered by `scripts/smoke_backup_restore.py` and `backend/tests/test_backup_scripts.py`. Do not put a live dump, a checksum of customer data, or a production secret into the repo to make a check pass.
