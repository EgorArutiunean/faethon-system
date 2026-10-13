# Release change inventory — 2026-10-11

Purpose: classify every tracked modification and untracked file in the working
tree before creating a release candidate. This is a scope decision, not evidence
that the tree is clean or ready to deploy.

Decision labels:

- **RC** — include in the candidate after review and green checks;
- **RC / known limitation** — include, but track the named follow-up;
- **Exclude** — must remain outside Git/release artifacts.

## Catalog and category hardening

| Files | Decision | Reason / evidence |
| --- | --- | --- |
| `backend/app/services/directory_service.py` | RC | Full ancestor traversal rejects indirect category cycles. |
| `backend/tests/test_product_groups.py` | RC | Covers three-level hierarchy and indirect-cycle rejection. |
| `frontend/src/pages/Products.tsx` | RC | Recursive category UI and restored price-control fields. |
| `frontend/src/i18n.tsx` | RC | RU/EN text for the catalog changes. |
| `frontend/src/styles.css` | RC | Styles required by the revised catalog UI. |
| `frontend/e2e/manager-workflows.spec.ts` | RC | Adds `CAT-01` browser coverage. |
| `backend/app/api/routes/products.py`, `backend/app/schemas/products.py`, `frontend/src/lib/api.ts`, `frontend/src/pages/Products.tsx`, `frontend/src/pages/DocumentEditor.tsx`, `frontend/src/pages/Dashboard.tsx` | RC | `PERF-01`: bounded server-side product page/search/sort/category filtering, exact totals/group counts and a separate bounded product lookup for document editing. The legacy list route remains for API compatibility. |

## Registry pagination and bounded lookups

| Files | Decision | Reason / evidence |
| --- | --- | --- |
| `backend/app/api/routes/documents.py`, `backend/app/schemas/documents.py`, `frontend/src/pages/Documents.tsx` | RC | `PERF-02`: document registry uses bounded server-side search, filters, whitelist sort and `items + total + offset + limit`. |
| `backend/app/api/routes/partners.py`, `backend/app/schemas/partners.py`, `backend/app/services/payments_service.py`, `frontend/src/pages/Partners.tsx`, `frontend/src/pages/Payments.tsx`, `frontend/src/pages/DocumentEditor.tsx`, `frontend/src/pages/Dashboard.tsx` | RC | `PERF-02/03`: paged partner registry, balances scoped to the visible page, exact dashboard partner total and bounded role-aware partner lookup in transactional forms. Balance aggregation is completed under `PERF-05`. |
| `backend/tests/test_auth_permissions.py`, `frontend/e2e/manager-workflows.spec.ts` | RC | Covers page totals/search/filter/sort, scoped balances and browser API contract compatibility. |

## Dashboard aggregates

| Files | Decision | Reason / evidence |
| --- | --- | --- |
| `backend/app/api/routes/dashboard.py`, `backend/app/services/dashboard_service.py`, `backend/app/schemas/dashboard.py`, `backend/app/main.py` | RC | `PERF-04`: permission-aware, period-filtered SQL aggregates with a bounded recent-document feed replace full-list dashboard loading. |
| `frontend/src/pages/Dashboard.tsx`, `frontend/src/lib/api.ts`, `frontend/e2e/manager-workflows.spec.ts` | RC | Dashboard consumes one summary contract and no longer downloads products, partners, documents, payments and stock lists to calculate metrics. |

## Balance query optimization

| Files | Decision | Reason / evidence |
| --- | --- | --- |
| `backend/app/services/payments_service.py`, `backend/app/services/reports_service.py` | RC | `PERF-05`: partner balances are calculated with grouped document/payment aggregates instead of two queries per partner. |
| `backend/tests/test_reports.py` | RC | Regression test proves balances and partner-debt report remain at exactly three SELECTs for 20+ partners. |

## Cash book pagination

| Files | Decision | Reason / evidence |
| --- | --- | --- |
| `backend/app/api/routes/cash.py`, `backend/app/schemas/cash.py`, `backend/app/services/cash_service.py`, `frontend/src/lib/api.ts`, `frontend/src/pages/Cash.tsx` | RC | `PERF-06`: bounded server-side cash-book pages replace the hidden 1000-row ceiling and expose exact total, current balance and page opening/closing balances while preserving the absolute running balance across pages. The legacy endpoint remains compatible without truncation. |
| `backend/tests/test_cash_service.py`, `frontend/e2e/manager-workflows.spec.ts` | RC | Regression coverage verifies page-boundary balances, cancelled-operation semantics and browser API contract compatibility. |

## Stock report pagination

| Files | Decision | Reason / evidence |
| --- | --- | --- |
| `backend/app/api/routes/reports.py`, `backend/app/services/reports_service.py`, `backend/app/schemas/reports.py`, `frontend/src/lib/api.ts`, `frontend/src/pages/Reports.tsx` | RC | `PERF-11`: the interactive stock-balances report returns bounded pages with exact row count and full filtered quantity total calculated in SQL; the export path remains complete. Local stock-report p95 improved from 5.73 s to 545 ms. |
| `backend/tests/test_reports.py` | RC | Regression coverage verifies page boundaries, exact total and aggregate quantity across all matching rows. |

## PostgreSQL performance baseline

| Files | Decision | Reason / evidence |
| --- | --- | --- |
| `backend/scripts/seed_performance_data.sql`, `backend/scripts/explain_performance_queries.sql` | RC | `PERF-07`: guarded, reproducible synthetic PostgreSQL dataset and read-only plans for core registries, balances, dashboard and cash book. |
| `docs/performance-baseline-2026-10-11.md` | RC | Records dataset, query timings, plan findings, proposed index scope and the independently discovered Alembic model/schema drift. |
| `backend/alembic/versions/0017_performance_indexes.py`, `backend/app/models/products.py`, `backend/app/models/partners.py`, `backend/app/models/documents.py`, `backend/app/models/accounting.py` | RC | `PERF-08`: reviewed B-tree, composite and PostgreSQL trigram indexes are represented in both the migration chain and ORM metadata. |
| `backend/alembic/versions/0018_reconcile_model_schema.py`, `backend/app/models/identity.py`, `backend/app/models/products.py`, `backend/app/models/documents.py` | RC | `CICD-04`: reconciles historical nullability/index drift with guarded backfills, preserves existing unique constraints, and makes both `0013 -> head` and `alembic check` green on PostgreSQL. |
| `backend/app/api/routes/documents.py` | RC | Rewrites document number/partner infix search into indexed union branches; measured execution improved from 123.6 ms to about 2.1 ms on the fixed synthetic dataset. |
| `backend/scripts/load_test.py`, `docs/load-test-baseline-2026-10-11.md` | RC | `PERF-09/10/11`: guarded concurrent endpoint runner and recorded p50/p95/p99/error-rate evidence. After report pagination, regular and report profiles both pass their local SLO with 0% errors. |

## Production configuration, authentication and health

| Files | Decision | Reason / evidence |
| --- | --- | --- |
| `.env.example`, `.env.production.example` | RC | Explicit runtime environment, demo-mode separation and safe production template. |
| `backend/app/core/config.py` | RC | Rejects weak production secret and non-HTTPS CORS. |
| `backend/app/services/auth_seed.py`, `backend/scripts/seed_demo.py` | RC | Production refuses demo accounts. |
| `backend/scripts/bootstrap_admin.py` | RC | One-time non-destructive administrator bootstrap. |
| `backend/alembic/versions/0014_user_password_change.py`, `backend/app/models/identity.py` | RC | Persists mandatory password-change state for bootstrap and admin resets. |
| `backend/alembic/versions/0015_login_lockout.py` | RC | Persists failed-attempt counter and lock expiration across restarts/instances. |
| `backend/alembic/versions/0016_token_revocation.py`, `backend/app/core/security.py` | RC | Versioned JWT revocation on logout and password changes. |
| `backend/app/api/routes/auth.py`, `backend/app/api/deps.py`, `backend/app/schemas/auth.py`, `backend/app/schemas/users.py`, `backend/app/services/users_service.py` | RC | Self-service password change and permission lock until completion. |
| `backend/app/api/routes/health.py` | RC | Liveness and DB/schema-aware readiness. |
| `backend/tests/test_health.py`, `backend/tests/test_production_security.py`, `backend/tests/test_auth_permissions.py`, `backend/tests/test_users.py`, `backend/tests/test_logistics_access.py` | RC | Regression evidence for readiness, production safeguards and temporary-password lifecycle. |
| `frontend/src/pages/Login.tsx`, `frontend/src/pages/ChangePassword.tsx`, `frontend/src/auth.tsx`, `frontend/src/components/ProtectedRoute.tsx`, `frontend/src/main.tsx`, `frontend/src/vite-env.d.ts` | RC | Demo credentials appear only in demo builds; temporary-password users are routed through mandatory change. |
| `backend/Dockerfile`, `backend/Dockerfile.prod`, `frontend/Dockerfile`, `frontend/Dockerfile.prod`, `frontend/nginx.conf` | RC | Production build forces demo mode off; Python/Node/nginx bases are digest-pinned and runtime containers are non-root (`app`/`nginx`); unsafe query-bearing Uvicorn access log is disabled. |
| `backend/app/core/observability.py`, `backend/tests/test_observability.py` | RC | JSON request logs, validated/generated correlation ID, safe field allowlist and regression tests preventing query/auth logging. |
| `backend/app/core/metrics.py`, `backend/app/api/routes/metrics.py`, `backend/tests/test_metrics.py` | RC | Internal Prometheus exposition for HTTP count/status/latency/active requests and SQLAlchemy pool state; excluded from OpenAPI and public nginx proxy. |
| `backend/app/core/error_tracking.py`, `backend/tests/test_error_tracking.py` | RC / activation pending | Sentry is opt-in by DSN, tags release/environment/request-id, disables default PII and strips request body, headers, cookies, query and user before send. Real staging event smoke remains required. |
| `ops/prometheus/prometheus.yml`, `ops/prometheus/alerts.yml` | RC / deployment pending | Internal scrape and ten officially validated rules for availability, 5xx, p95, DB pool plus local/offsite backup failure and freshness. Alertmanager receiver and delivery drill remain external gates. |
| `ops/grafana/dashboards/buy-modern-overview.json`, `docs/observability-runbook.md` | RC / deployment pending | Importable API/DB/disk/backup dashboard and incident response procedure. Datasource, node exporter and live dashboard validation remain required. |
| `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.prod-e2e.yml` | RC | Propagates runtime mode, uses readiness healthchecks, pins PostgreSQL 16 by digest, applies production resource/log limits, and blocks backend startup until a one-shot Alembic migration succeeds. Clean production startup smoke reached revision `0018` and readiness `200`. |

## CI/CD

| Files | Decision | Reason / evidence |
| --- | --- | --- |
| `.github/workflows/ci.yml`, `backend/tests/test_postgres_accounting_core.py` | RC | `CICD-03..10`: migration/accounting coverage, exact-image E2E, SHA-pinned actions, dependency review/audits, CodeQL, Trivy, SPDX SBOM and 30-day evidence artifacts. First GitHub run still required. |
| `backend/pyproject.toml`, `backend/pytest.ini`, `backend/requirements-dev.in`, `backend/requirements-dev.txt` | RC | `CICD-01/02`: pinned Ruff/mypy/pytest-cov toolchain, formatter/lint/full-project typecheck gates and 82.5% branch coverage baseline. The original 13-module gradual mypy allowlist is fully removed. |
| `.github/workflows/release.yml` | RC | `CICD-11..13`: GHCR publication from a validated full `main` SHA with a successful push CI run, immutable version/SHA tags without `latest`, registry digest resolution and a 90-day JSON release manifest. First real publish still required. |
| `docker-compose.release.yml`, `backend/scripts/release_smoke.py`, `.github/actionlint.yaml` | RC / infrastructure pending | Image-only staging topology, authenticated external smoke and custom runner contract. Release workflow deploys exact GHCR digests and stores a `staging-passed` manifest; first real host/runner/environment run remains required. |
| `.github/workflows/release.yml` production job | RC / environment pending | Promotes the exact staging-tested digests after explicit request and protected environment approval; validates UAT, backup and rollback references, runs migration/readiness/authenticated smoke, and stores a production manifest. |
| `.github/workflows/rollback.yml` | RC / production drill pending | Protected application-only rollback to exact previous digests; blocks schema-incompatible rollback, never downgrades DB, runs authenticated smoke and stores 365-day evidence. Local no-migration rollback drill passed on revision `0018`. |
| `.github/workflows/ci.yml` workflow-lint job | RC | Pinned actionlint image validates all workflow expressions and the declared self-hosted runner label. |
| `docker-compose.prod-e2e.yml`, `frontend/playwright.prod.config.ts`, `frontend/e2e-real/prod-docker-environment.ts`, `frontend/e2e-real/global-teardown-prod.ts` | RC | Reproducible ephemeral production-image harness: clean PostgreSQL, one-shot migration/seed, readiness, nginx-routed E2E and guaranteed teardown. Local result: `8 passed`. |
| `frontend/e2e-real/manager-sale.spec.ts` | RC | `CICD-00/06`: all eight PostgreSQL browser scenarios pass through production nginx on schema head `0018`; LOG-01 covers mandatory temporary-password change and fresh token after revocation. |
| `frontend/src/pages/DocumentEditor.tsx` | RC | Preserves the existing product name when a correction line is edited while bounded product options refresh asynchronously; regression was found by exact-image M08 and verified by the green rerun. |
| `backend/requirements.in`, `backend/requirements.txt`, `backend/requirements-dev.in`, `backend/requirements-dev.txt` | RC | Separates exact-version runtime and test/tooling locks; local `pip-audit` reports no known vulnerabilities. Wheel hashes remain follow-up work for a controlled mirror. |
| `frontend/package.json`, `frontend/package-lock.json` | RC / known limitation | Adds deterministic production E2E and pins the resolved Node tree. Production-only audit is clean; 7 dev-only findings in the Tailwind 3 build chain require migration or signed risk acceptance. |
| `docs/ci-cd-technical-spec.md` | RC | Implementation contract for PR, release, staging, production and rollback pipelines. |

## Backup and restore

| Files | Decision | Reason / evidence |
| --- | --- | --- |
| `scripts/backup_postgres.sh`, `scripts/backup_postgres.ps1` | RC | Atomic dump, validation/checksum, Compose-label discovery without host DB secrets, exact-pattern retention and atomic success/failure node-exporter metrics. Runtime project-label backup smoke passed. |
| `scripts/offsite_backup.sh` | RC / repository pending | Verifies the newest dump/checksum pair, sends it to an existing client-side encrypted Restic repository and publishes independent atomic metrics. Real storage credentials, object lock and restore drill remain external gates. |
| `ops/systemd/buy-modern-backup.service`, `ops/systemd/buy-modern-backup.timer`, `ops/systemd/backup.env.example`, `docs/backup-operations.md` | RC / host activation pending | Hourly RPO-oriented schedule, hardened service, 14-day retention configuration and operator runbook. Production installation and enablement remain required. |
| `scripts/restore_postgres.sh`, `scripts/restore_postgres.ps1` | RC | Preflight/checksum validation and explicit env-file. |
| `docs/restore-drill-2026-10-12.md` | RC evidence | Separate-database restore, reconciliation, readiness/login/dashboard smoke and measured local restore duration. |
| `.gitignore` | RC | Excludes dumps, local backup directory and legacy working artifacts. |

## Import resource safety

| Files | Decision | Reason / evidence |
| --- | --- | --- |
| `backend/app/api/routes/imports.py`, `backend/app/services/import_service.py`, `backend/tests/test_import_lite.py` | RC | Streaming body limit, row limit, file allowlist and XLSX archive safeguards. |
| `frontend/nginx.conf` | RC | Aligns reverse-proxy upload ceiling with backend default (10 MiB). |

## Release and legacy documentation

| Files | Decision | Reason / evidence |
| --- | --- | --- |
| `README_DEPLOY.md` | RC | Current NO-GO, safe bootstrap and backup/restore procedure; obsolete force-push removed. |
| `docs/deployment-readiness-2026-10-10.md`, `docs/deployment-work-plan.md`, `docs/release-change-inventory-2026-10-11.md` | RC | Audit, authoritative living release gate and explicit change classification. |
| `docs/project-status.md`, `docs/release-plan.md`, `docs/re-audit-and-work-plan-2026-09-01.md` | RC | Historical claims are labelled and point to the current tracker. |
| `docs/full-project-report-2026-09-04.md` | RC | Technical/portfolio report, corrected to React 19 and current test context. |
| `docs/catalog-import-plan.md` | RC | Migration design; commercial XLSX remains excluded and provenance is explicitly unverified. |
| `docs/legacy-data-readiness.md` | RC | Catalog-only GDB scope and separate signed opening balances. |
| `docs/legacy-analysis/buysell-to-modern-map.md` | RC | Records confirmed `STOVAR`, `SGRP`, `SEDIZM` preview findings. |
| `docs/legacy-analysis/connection-notes.md`, `docs/legacy-analysis/file-inventory.md` | RC | Sanitised technical evidence without workstation path, hostname or literal legacy password. |
| `docs/legacy-analysis/gdb-recovery-plan.md` | RC | Safe export route and actual InterBase registration blocker. |

## Explicitly excluded artifacts

| Artifact | Decision | Control |
| --- | --- | --- |
| `Лист10309.xlsx` and any price-list/source XLSX | Exclude | Commercial input; ignored by Git. Record hash/provenance only. |
| `BUY.GDB`, copies, FirstAID working files and extracted PII | Exclude | Legacy/PII data; keep outside Git and operate only on disposable copies. |
| `.env`, `.env.production`, bootstrap passwords and runtime secrets | Exclude | Deployment-secret mechanism only. |
| `backups/`, `*.dump`, checksum sidecars generated at runtime | Exclude | Operational artifacts; ignored locally and stored in controlled backup storage. |

## Proposed commit split

1. `catalog: harden nested categories and price controls`
2. `security: harden production auth configuration and readiness`
3. `ops: validate PostgreSQL backup and restore artifacts`
4. `performance: paginate core registries and bounded lookups`
5. `docs: reconcile deployment and legacy migration evidence`

Do not create the RC tag until all four commits pass the mandatory CI matrix,
real PostgreSQL E2E and exact production-image smoke.
