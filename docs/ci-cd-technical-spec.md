# Техническое задание на CI/CD Buy Modern

## Актуальный способ доставки: Coolify (2026-10-14)

Развёртывание выполняется на существующем Coolify по инструкции
[coolify-deployment.md](coolify-deployment.md). `release.yml` по умолчанию
использует `delivery=coolify-manual`: публикует GHCR images и manifest, после
чего оператор переносит точную пару digest'ов в Coolify, выполняет Deploy и
фиксирует smoke/UAT. Автоматический вызов Coolify API пока не реализован.
Описанные ниже self-hosted runners — альтернативный legacy-путь, доступный
только при `delivery=legacy-self-hosted`. Его approvals и rollback не защищают
ручные операции в Coolify; production GO и права доступа обеспечиваются отдельно.

## Исходная спецификация legacy delivery

Версия: 1.0
Дата: 2026-10-13
Статус: implementation draft; staging workflow подготовлен, инфраструктурная
активация и production workflow требуют согласования DevOps/QA/product owner.

## 1. Цель

Построить воспроизводимый delivery-процесс, при котором production получает
ровно те же immutable container images, которые прошли staging, а каждое
изменение имеет проверяемую цепочку: commit → tests → image digest → migration
revision → approval → deployment → smoke evidence.

Production deployment из локального рабочего дерева, ветки разработчика или
повторной сборки на сервере запрещён.

## 2. Исходные условия

- исходный код: GitHub, protected `main`;
- CI: GitHub Actions;
- runtime: Docker Compose, nginx, FastAPI, PostgreSQL 16;
- schema migrations: Alembic, одна head revision;
- выбранный registry: GHCR; публикация выполняется GitHub Actions через
  scoped `GITHUB_TOKEN` с `packages: write`;
- environments: `staging`, `production`;
- deployment unit: backend image + frontend/nginx image + migration revision;
- production secrets не хранятся в GitHub variables, artifacts, image layers,
  Compose-файлах или логах.

## 3. Роли и ответственность

| Роль | Ответственность в pipeline |
| --- | --- |
| Fullstack | Исправляет код/миграции, поддерживает Dockerfiles, unit/API tests, health contracts. |
| QA | Владеет smoke/E2E/UAT-наборами, критериями прохождения и release evidence. |
| DevOps | Registry, runners, environments, secrets, TLS, deploy/migration/rollback jobs, monitoring и backups. |
| Project owner | Scope, accepted limitations, release window, UAT sign-off и production approval. |

Автор изменения не должен быть единственным production approver.

## 4. Pull request pipeline

Триггеры: каждый `pull_request` в `main`; повторный run разрешён без изменения
артефактов. Для одного PR старый незавершённый run отменяется через concurrency.

Обязательные jobs:

1. **Repository hygiene**
   - secret scan;
   - запрет GDB/XLSX/dump/.env и файлов сверх утверждённого размера;
   - dependency review для PR.
2. **Backend quality**
   - Python 3.12;
   - Ruff check + format check;
   - статическая типизация выбранным инструментом после фиксации baseline;
   - `compileall`;
   - pytest + coverage XML/JUnit;
   - согласованный coverage gate, стартовая цель не ниже текущего baseline.
3. **Frontend quality**
   - Node 22, `npm ci`;
   - typecheck, production build;
   - dependency audit с утверждённой severity policy;
   - mock Playwright, включая `CAT-01`.
4. **PostgreSQL integrity**
   - чистый PostgreSQL 16;
   - upgrade предыдущей release revision → head;
   - `alembic check` и проверка единственной head;
   - PostgreSQL concurrency/integrity tests;
   - критические document/stock/payment/cash scenarios на PostgreSQL.
5. **Production image smoke**
   - build production Dockerfiles;
   - запуск frontend/nginx + backend + PostgreSQL без bind mounts;
   - migrations отдельным one-shot job;
   - `/health/live`, `/health/ready`, login и критический smoke через nginx.
6. **Security/supply chain**
   - SAST и dependency scan;
   - container vulnerability scan;
   - SBOM CycloneDX или SPDX для обоих images;
   - запрет critical vulnerabilities; high — блокирует либо требует
     документированного risk acceptance с датой истечения.

Required checks на branch protection: все перечисленные jobs. Merge запрещён
при skipped/cancelled/failed обязательном check.

## 5. Main/release pipeline

Триггер: merge в `main`; release candidate — вручную или по подписанному tag
`vX.Y.Z-rc.N`.

1. Повторить обязательные проверки без доверия к artifacts из чужого fork.
2. Собрать backend/frontend images один раз.
3. Присвоить теги `vX.Y.Z-rc.N`, `sha-<full-or-approved-short-sha>`; `latest`
   не используется для deployment.
4. Push в registry и получить registry digest `sha256:...`.
5. Создать SBOM, provenance/attestation и подписать images выбранным механизмом.
6. Сформировать release manifest: Git SHA, digests, Alembic head, SBOM links,
   test run URLs, build timestamp и actor.
7. Автоматически развернуть **по digest** в staging без rebuild.
8. Выполнить staging migrations one-shot job, дождаться readiness и запустить
   production-image E2E/smoke.
9. Сохранить результаты и пометить RC как `staging-passed` только после green.

## 6. Production deployment

Триггер: manual approval в protected GitHub Environment `production` только
для manifest со статусом `staging-passed`.

Pre-deploy gates:

- подписанный UAT и GO/NO-GO;
- backup не старше согласованного RPO и checksum/restore evidence;
- свободное место и доступность БД;
- secrets/TLS/domain/monitoring проверены;
- нет открытых P0; P1 имеют письменное risk acceptance;
- указан rollback target — предыдущий manifest/digests.

Порядок:

1. Получить deployment lock/concurrency group `production`.
2. Зафиксировать pre-deploy backup ID.
3. Запустить Alembic migration как отдельный контейнер exact backend digest.
4. Обновить сервисы на digests из manifest.
5. Дождаться readiness; выполнить technical smoke через внешний HTTPS URL.
6. QA/оператор выполняет минимальный business smoke.
7. Записать deployment record и начать hypercare monitoring.

Никаких `docker compose build`, `git pull` или ручного редактирования файлов на
production-сервере.

## 7. Rollback

- Application rollback переключает backend/frontend на digests предыдущего
  подтверждённого manifest.
- Миграции по умолчанию проектируются backward-compatible (expand/migrate/contract).
- Автоматический `alembic downgrade` в production запрещён.
- Если миграция необратима или испортила данные, применяется утверждённый
  restore runbook; решение принимает incident owner вместе с business owner.
- Целевые RPO/RTO: `<= 1 час` / `<= 2 часа`, подтверждаются restore drill.

## 8. Secrets и environments

Минимальные production secrets:

- registry/deployment credentials;
- `POSTGRES_PASSWORD` / `DATABASE_URL`;
- `AUTH_SECRET_KEY`;
- bootstrap admin values только на время первого bootstrap;
- backup storage credentials;
- monitoring/error-tracking credentials.

Требования:

- разные secrets для staging/production;
- least privilege и ротация;
- masking в CI logs;
- pull requests из forks не получают environment secrets;
- bootstrap password удаляется сразу после использования и смены пароля.

## 9. Artifacts и retention

Для каждого RC хранить:

- JUnit, coverage, Playwright HTML/traces/screenshots;
- migration logs и schema revision;
- image digests, SBOM, vulnerability reports, provenance;
- release/deployment manifest;
- UAT, approver и GO/NO-GO record;
- backup ID и restore-drill evidence.

Рекомендуемый retention: PR evidence 14–30 дней, RC/release evidence не менее
12 месяцев либо по внутренней политике компании. Dumps и PII не являются CI
artifacts.

## 10. Наблюдаемость после deployment

Pipeline считается успешным только если после deploy:

- `/health/live` и `/health/ready` стабильны;
- нет всплеска 5xx/latency/login failures;
- PostgreSQL pool/disk доступны;
- backup age в норме;
- smoke transaction видна в audit log и очищена/маркирована по процедуре;
- alert channel проверен.

## 11. Acceptance criteria

- PR нельзя merge без required checks.
- Из одного Git SHA получается один однозначный набор image digests.
- Staging и production используют одинаковые digests.
- Migration job повторяем и не запускается скрыто при restart приложения.
- Production требует независимого manual approval.
- Failed readiness/smoke прекращает rollout.
- Предыдущая версия приложения восстанавливается по runbook.
- Отдельная БД успешно восстановлена из backup; RPO/RTO измерены.
- Release record позволяет за 10 минут установить: что, кем, когда и с какими
  тестами/миграцией/backup было развёрнуто.

## 12. Решения, которые нужно предоставить DevOps

1. Политика хранения опубликованных GHCR images и package visibility.
2. Для staging выбран Linux self-hosted runner с labels
   `self-hosted, linux, buy-modern-staging`; host/DNS/TLS и регистрация runner
   ещё должны быть предоставлены. Для production выбран отдельный runner с
   label `buy-modern-production`; его host и регистрация также ожидаются.
3. Public domain, TLS termination и DNS owner.
4. Secrets manager и approvers GitHub Environments.
5. Backup storage, encryption, retention и alert channel.
6. Monitoring/logging/error-tracking stack.
7. Release numbering и окно production deploy.

## 13. Подготовленная staging-реализация

- `.github/workflows/release.yml` после публикации передаёт digest'ы напрямую в
  job окружения `staging`; повторная сборка отсутствует.
- `docker-compose.release.yml` не содержит `build` и требует backend/frontend
  image references из workflow.
- runner materializes `STAGING_ENV_FILE` с mode `0600`, удаляет его и GHCR login
  после job; environment secrets не попадают в artifacts.
- deployment выполняет `pull`, one-shot migration, readiness wait, сверку
  Alembic head и внешний authenticated smoke health/login/me/dashboard.
- успешный job сохраняет `staging-passed` manifest на 365 дней; failure logs
  сохраняются отдельно и не должны содержать request body/query/auth headers.

Для активации создать GitHub Environment `staging`, variable
`STAGING_BASE_URL` и secrets `STAGING_ENV_FILE`, `STAGING_SMOKE_EMAIL`,
`STAGING_SMOKE_PASSWORD`, затем зарегистрировать dedicated runner. Smoke-user
должен заранее завершить обязательную смену временного пароля.

## 14. Подготовленная production promotion и rollback-реализация

Production job в `.github/workflows/release.yml` запускается только по явному
input `promote_to_production`, после green staging job и через GitHub Environment
`production`. До deployment он требует UAT reference, свежий backup ID и два
предыдущих rollback digest. Backend/frontend references берутся из тех же
publish outputs, что staging; повторная сборка отсутствует.

Для активации зарегистрировать dedicated runner с labels
`self-hosted, linux, buy-modern-production`, создать protected Environment
`production`, назначить независимых required reviewers, задать variable
`PRODUCTION_BASE_URL` и secrets `PRODUCTION_ENV_FILE`,
`PRODUCTION_SMOKE_EMAIL`, `PRODUCTION_SMOKE_PASSWORD`.

`.github/workflows/rollback.yml` выполняет только application rollback. Перед
переключением он сравнивает Alembic head целевого backend image с текущей
revision БД. При несовпадении rollback блокируется и требует отдельного решения
incident owner: forward fix либо утверждённый restore. Workflow не выполняет
`alembic downgrade`, запускает backend/frontend с `--no-deps`, повторяет внешний
smoke и сохраняет immutable rollback record на 365 дней.
