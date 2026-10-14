# Changelog

## 0.1.0-rc.2 — 2026-10-14

Security refresh для первого Coolify staging. Не является production GO.

- Обновлены runtime `curl` и `libcurl4t64` до `8.14.1-2+deb13u7`:
  исправления CVE-2026-8286 и CVE-2026-8927 из Debian security.
- Publish workflow проверяет именно публикуемую пару образов Trivy до push,
  блокирует найденные исправляемые HIGH/CRITICAL и сохраняет JSON-отчёты.
- Включены managed Coolify Compose, инструкция и изолированный smoke-тест.
- Схема БД без изменений: `0018_reconcile_model_schema`.
- RC1 больше не рекомендуется для нового развёртывания после security finding
  в [CI от 2026-10-14](https://github.com/EgorArutiunean/faethon-system/actions/runs/38620751213).

Результаты CI и публикации фиксируются отдельно в release evidence.

## 0.1.0-rc.1 — 2026-10-13

Первый формально квалифицированный release candidate Buy Modern. Статус:
готов для staging/UAT, но не является разрешением на production cutover с
реальными финансовыми данными.

### Added

- Полные сценарии закупки, продажи, перемещения, платежей, кассы, склада,
  отчётов и импорта с ролевым доступом и аудитом.
- Иерархический каталог, контроль закупочной/продажной цены и защита от циклов.
- Обязательная смена временного пароля, persistent login lockout и token
  revocation.
- Dashboard, JSON logs, request IDs, Prometheus metrics, Sentry integration и
  Grafana dashboard.
- PostgreSQL migrations до `0018_reconcile_model_schema` и PostgreSQL integrity
  tests.
- Immutable-image staging/production workflows, manual promotion и rollback.
- Валидируемые локальные backups, Restic offsite step, restore runbook и
  backup freshness alerts.

### Verification

- Backend: `211 passed, 4 skipped`, branch coverage `83.05%`.
- PostgreSQL migration/accounting integrity: `4 passed`.
- Playwright mock UI: `5 passed`.
- Playwright production-like nginx/FastAPI/PostgreSQL: `8 passed`.
- Ruff, formatting, mypy, compileall, actionlint and Compose validation passed.
- Trivy repository, dependency locks and production images: no
  HIGH/CRITICAL findings.

### Known release gates

- Publish images and manifest to GHCR from a protected GitHub workflow.
- Deploy the exact digests to a real HTTPS staging environment.
- Configure external Sentry, Prometheus/Grafana and Alertmanager receivers.
- Configure the real encrypted offsite repository and complete an offsite
  restore drill.
- Complete catalog reconciliation, UAT, RPO/RTO approval and signed GO/NO-GO.
