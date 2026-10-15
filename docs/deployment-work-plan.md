# Buy Modern: живой план подготовки к деплою

Последнее обновление: 2026-10-15
Связанный аудит: [deployment-readiness-2026-10-10.md](deployment-readiness-2026-10-10.md)
Текущее решение: **GO для demo/UAT; NO-GO для production**.

Этот файл — единый трекер релизных работ. После завершения задачи меняем
`[ ]` на `[x]` и добавляем ссылку на commit, CI run, отчёт или другой артефакт.

## Обозначения

- `[x]` — выполнено и подтверждено;
- `[ ]` — не выполнено;
- **BLOCKED** — требуется внешнее решение или доступ;
- **P0** — блокирует production;
- **P1** — обязательно до эксплуатации с реальными данными;
- **P2** — улучшение после первого стабильного релиза.

## Сводный статус

| Этап | Статус | Владелец | Условие завершения |
|---|---|---|---|
| A. Аудит и исходная проверка | Выполнен | Fullstack + QA | Зафиксированы факты и блокеры |
| 0. Release baseline | Выполнен | Fullstack + QA + Project | Чистый RC SHA/tag |
| 1. Security и runtime | В работе | Fullstack + DevOps | Нет demo-доступа, работают probes/TLS |
| 2. Legacy migration | Частично / BLOCKED | Fullstack/Data + Project | Повторяемый импорт и сверка |
| 3. Производительность | Выполнен локально | Fullstack + QA | Рабочий объём проходит SLO; нужен staging rerun |
| 4. CI/CD и staging | Частично | DevOps + QA | Деплой exact images по digest |
| 5. Backup и observability | В работе | DevOps + QA | Restore drill и alerts |
| 6. UAT и rehearsal | Не начат | QA + Project + оператор | Подписанный GO/NO-GO |
| 7. Cutover и hypercare | Не начат | Project + DevOps | Production принят бизнесом |

## Текущий фокус

### Согласованный порядок на 15–16 октября 2026

**Сегодня, 15 октября — эксплуатационная готовность staging:**

- [ ] Сверить фактические backend/frontend image digest'ы с RC2 и определить
  точный Compose project PostgreSQL, не затрагивая другие Coolify-ресурсы.
- [ ] Выполнить первый локальный backup, проверить SHA-256 и читаемость dump.
- [ ] Провести restore drill в отдельном контейнере/volume, не поверх staging DB.
- [ ] Установить и проверить расписание backup; записать путь и владельца job.
- [ ] Выбрать внешнее хранилище и настроить зашифрованную offsite-копию;
  проверить получение и восстановление этой копии.
- [ ] Выбрать канал уведомлений; проверить доставку тестового alert и recovery,
  контроль доступности, свободного диска/RAM и давности последнего backup.

**Завтра, 16 октября — бизнес-проверки:** закупка/приход, продажа/оплата,
возвраты, остатки, суммы и права пользователей. До их приёмки production GO
не выдаётся. Этот порядок — план работ, а не автоматически запланированный запуск.

Доступ к host пока через терминал оператора. Секреты не передавать в чат.
Offsite destination и канал уведомлений требуют выбора оператора; локальная
копия на том же VPS не считается выполненным offsite backup.

### Выполнено без терминала сервера (15 октября)

- [x] Restore теперь требует checksum, точный project/database и подтверждение;
  отказывается от непустой БД, не выполняет `--clean`.
- [x] Добавлен атомарный rollback restore при ошибке; устранена зависимость
  проверки checksum от текущей директории и shell interpolation в PS restore.
- [x] Backup защищён от параллельного запуска и перезаписи timestamp;
  retention ограничен точным форматом имён, checksum offsite проверяет сам dump.
- [x] Локально пройдены тесты скриптов и реальный синтетический PostgreSQL drill
  (PowerShell + POSIX restore), временные БД удалены.
- [x] Полная backend-регрессия: `234 passed, 4 skipped`; targeted backup/restore:
  `27 passed`; Ruff, actionlint и проверки синтаксиса пройдены.
- [x] Подготовлены CI job, исправления systemd template и инструкция.
- [x] Новый `backup-restore` job и весь push-CI прошли на commit
  [`048327f`](https://github.com/EgorArutiunean/faethon-system/commit/048327f7bea61088cf1255d9034719eeac8567d2):
  [CI #19](https://github.com/EgorArutiunean/faethon-system/actions/runs/38720082325).
- [ ] Новый systemd unit проверен в runtime и установлен на целевом сервере.

Подробности и ограничения: [evidence локальных проверок](backup-safety-2026-10-15.md).
Эти отметки не закрывают backup/restore реального staging, offsite и alert delivery.

### Release gates

1. `CICD-14..CICD-15` — завершить сверку digest'ов и приёмку запущенного staging:
   [пошаговая инструкция](coolify-deployment.md); отдельный GitHub runner не нужен.
2. `SEC-13` — завершить TLS/HSTS/CSP edge hardening на целевой инфраструктуре.
3. `DATA-01..DATA-07` — принять решения по opening data и mapping.
4. `UAT-01..UAT-18` — провести бизнес-приёмку и rehearsal на опубликованных RC digest'ах.
5. `CICD-17..CICD-18` — ограничить production-доступ в Coolify, фиксировать GO
   и продвигать проверенные digest'ы без rebuild.

## Coolify delivery (2026-10-14)

- [x] Добавлены image-only Compose без host ports, env-шаблон и инструкция.
- [x] Publish workflow по умолчанию не запускает legacy self-hosted deploy jobs.
- [x] RC2 опубликован после security refresh curl/libcurl; полный CI и
  сканирование именно публикуемых образов прошли. [Evidence](release-rc2-security.md).
- [x] Внешние HTTPS live/ready probes ответили 200, database=ok,
  schema_revision=`0018_reconcile_model_schema` (2026-10-15).
- [x] Оператор подтвердил создание администратора и успешный вход (2026-10-15).
- [x] Локальные actionlint/Compose validation и изолированный smoke пройдены:
  миграции, bootstrap/смена пароля, HTTP smoke, сохранность volume и блокировка
  старта при ошибке миграции. См. раздел 14 [инструкции](coolify-deployment.md).
- [ ] Конфигурация проверена на установленной версии Coolify и целевом сервере.
- [ ] Staging resource, отдельный volume, секреты, домен и TLS настроены.
- [ ] Образы по digest, миграция, bootstrap и внешний smoke проверены на staging.
- [ ] Backup/restore и UAT выполнены; принято production GO/NO-GO.
- [ ] Автоматизация Coolify API: обновление digest'ов, deploy, ожидание, smoke.

Первый запуск выполняется вручную через Coolify. Старые пункты и записи про
self-hosted runner ниже описывают прежнюю реализацию, а не требование новой схемы.
RC1 сохранён для истории, новый рекомендуемый baseline — RC2 на SHA
`3f150991e334540643c2b6c5be562bba6087fbed`. Деплой в Coolify выполнен оператором;
агент не запускал remote deploy. Фактические digest'ы запущенных контейнеров,
полный авторизованный smoke и backup/restore ещё требуют подтверждения.

## A. Аудит и исходная проверка

- [x] Проверена архитектура backend/frontend.
- [x] Подтверждён стек: React 19, TypeScript, FastAPI, SQLAlchemy, PostgreSQL 16.
- [x] Подтверждена одна Alembic head: `0018_reconcile_model_schema`.
- [x] Backend SQLite suite после catalog/security/auth/import/performance hardening:
  `196 passed, 4 PostgreSQL-only skipped`; отдельная PostgreSQL matrix: `4 passed`.
- [x] Frontend TypeScript check пройден.
- [x] Frontend production build пройден.
- [x] Mock Playwright: `5 passed`, включая `CAT-01` и `SEC-06`.
- [x] Production Compose успешно разобран с тестовыми env values.
- [x] Подтверждено наличие 5 mock и 8 real E2E scenarios.
- [x] Release/legacy-документы приведены к текущему scope; локальные пути,
  hostname и literal legacy password удалены из публичных заметок.
- [x] Real PostgreSQL E2E повторён в изолированном Compose-контуре: `8 passed`.
- [x] Exact production-container smoke повторён на текущем working tree:
  production Dockerfiles, nginx, backend и PostgreSQL, `8 passed`; после теста
  контейнеры и сеть удалены. Повтор на чистом RC SHA остаётся финальным gate.

## 0. Release baseline — P0

Ответственные: Fullstack, QA, Project.
Оценка: 1–2 рабочих дня.

- [x] **REL-01:** классифицировать и осознанно включить, разделить или исключить все modified/untracked файлы (`release-change-inventory-2026-10-11.md`).
- [x] **REL-02:** проверить catalog WIP на функциональные регрессии.
- [x] **REL-03:** вернуть себестоимость, наценку и price warning.
- [x] **REL-04:** запретить косвенные циклы категорий (`A -> B -> A`).
- [x] **REL-05:** добавить backend/UI tests для nested categories.
- [x] **REL-06:** перенести новые hardcoded RU-строки каталога в i18n.
- [ ] **REL-07:** согласовать scope релиза и accepted limitations.
- [x] **REL-08:** получить чистое рабочее дерево.
- [x] **REL-09:** создать RC commit series и опубликовать tag
  [`v0.1.0-rc.1`](https://github.com/EgorArutiunean/faethon-system/releases/tag/v0.1.0-rc.1)
  на SHA `8dd7ff0c8135853dc56ca99e7e06a15fa06ea3e6`.
- [x] **REL-10:** подготовить `CHANGELOG.md` для RC.

Критерий завершения:

- [x] Один воспроизводимый SHA прошёл обязательные CI checks:
  [main push CI #13](https://github.com/EgorArutiunean/faethon-system/actions/runs/38375823933).
- [x] Deploy из незакоммиченного рабочего дерева запрещён workflow-проверками.

## 1. Security и runtime hardening — P0/P1

Ответственные: Fullstack, DevOps, QA.
Оценка: 3–5 рабочих дней.

- [x] **SEC-01 / P0:** добавить `APP_ENV`.
- [x] **SEC-02 / P0:** запретить запуск production с placeholder `AUTH_SECRET_KEY`.
- [x] **SEC-03 / P0:** запретить `seed_demo.py` и demo seed при `APP_ENV=production`.
- [x] **SEC-04 / P0:** убрать `admin@example.com / admin123` из production Login UI.
- [x] **SEC-05 / P0:** реализовать one-time bootstrap первого администратора.
- [x] **SEC-06 / P0:** требовать смену bootstrap/admin-reset временного пароля до доступа к рабочим операциям.
- [x] **SEC-07 / P0:** реализовать `/health/live`.
- [x] **SEC-08 / P0:** реализовать `/health/ready` с `SELECT 1` и проверкой schema revision.
- [x] **SEC-09 / P0:** readiness возвращает `503` при недоступной БД.
- [x] **SEC-10 / P1:** добавить persistent account lockout: 5 неудачных попыток / 15 минут по умолчанию, row lock и generic auth response.
- [x] **SEC-11 / P1:** access-only JWT без refresh для первого релиза; production TTL <= 60 минут; logout/password change/admin reset отзывают старые токены через persistent `token_version`.
- [x] **SEC-12 / P1:** backend limits: 10 MiB body, 20 000 строк, allowlist CSV/XLSX, ZIP entries/unpacked-size/compression/encryption checks.
- [ ] **SEC-13 / P1:** настроить HTTPS, HSTS и CSP. HSTS/CSP/security headers реализованы в production nginx; TLS certificate, HTTP->HTTPS redirect и public-URL smoke ожидают target infrastructure.
- [x] **SEC-14 / P1:** ограничить CORS явными production HTTPS-origin.

Критерий завершения:

- [ ] Production не стартует с demo credentials, слабым secret или неверным CORS.
- [ ] QA подтвердил authentication, authorization и failure-mode scenarios.

## 2. Legacy export и migration — P0

Ответственные: Fullstack/Data, QA, Project, бизнес-оператор.
Оценка: 5–10 рабочих дней после снятия блокирующих решений.

### Уже подтверждено

- [x] Создана безопасная read-only копия `BUY.GDB`.
- [x] Подтверждены InterBase 7.1 / ODS 11.1 и 68 relations.
- [x] Подтверждено отсутствие bad pages.
- [x] Найдены `STOVAR`, `SGRP`, `SEDIZM`.
- [x] Установлено, что `LICO` содержит PII и паспортные данные.

### Требуемые решения — BLOCKED

- [ ] **DATA-01:** решить: catalog-only pilot или полный финансовый cutover.
- [ ] **DATA-02:** подтвердить источник opening stock.
- [ ] **DATA-03:** подтвердить источник opening partner debts.
- [ ] **DATA-04:** подтвердить opening cash balance.
- [ ] **DATA-05:** утвердить cutoff date/time и владельца итогов.
- [ ] **DATA-06:** утвердить mapping складов и категорий.
- [ ] **DATA-07:** утвердить семантику учётной и розничной цены.

### Реализация

- [ ] **DATA-08:** выполнить минимизированный export `STOVAR`.
- [ ] **DATA-09:** выполнить минимизированный export `SGRP`.
- [ ] **DATA-10:** выполнить минимизированный export `SEDIZM`.
- [ ] **DATA-11:** не экспортировать полный `LICO`; оформить allowlist допустимых полей.
- [ ] **DATA-12:** добавить units в import pipeline.
- [ ] **DATA-13:** исправить mapping учётной/розничной цены.
- [ ] **DATA-14:** добавить staging tables и `import_batch_id`.
- [ ] **DATA-15:** обеспечить idempotency и bulk upsert.
- [ ] **DATA-16:** добавить журнал ошибок и файл исключений.
- [ ] **DATA-17:** выполнить dry-run на чистой staging DB.
- [ ] **DATA-18:** повторить apply дважды и подтвердить идемпотентность.
- [ ] **DATA-19:** проверить не менее 15 000 товаров.
- [ ] **DATA-20:** сверить counts, дубликаты, цены и суммы.
- [ ] **DATA-21:** подписать reconciliation report.

Критерий завершения:

- [ ] Импорт полностью повторяем из versioned manifest без ручной правки БД.
- [ ] PII не попадает в Git, логи, demo и лишние таблицы staging.
- [ ] Контрольные итоги подписаны владельцем бизнеса.

## 3. Производительность и корректность UI/API — P1

Ответственные: Fullstack, QA.
Оценка: 3–6 рабочих дней.

- [x] **PERF-01:** server-side pagination/search/sort для товаров. Каталог использует
  paged endpoint (`items + total + offset + limit`), whitelist-сортировку, поиск по
  имени/SKU и фильтр по дереву категорий; редактор документов использует отдельный
  ограниченный server-side lookup вместо загрузки `limit=500`.
- [x] **PERF-02:** server-side pagination/search/filter/sort для реестров документов
  и контрагентов; формы документов и оплат используют bounded partner lookup.
- [x] **PERF-03:** основные реестры товаров, документов и контрагентов используют
  ответы `items + total + offset + limit`; legacy list endpoints временно сохранены
  для обратной совместимости и будут удаляться только отдельной версионированной сменой API.
- [x] **PERF-04:** permission-aware aggregate endpoint для Dashboard считает периодические
  суммы/статусы, кассу, склад, справочники и ограниченную ленту последних документов
  без загрузки полных операционных списков в браузер.
- [x] **PERF-05:** устранён N+1 в partner balances и отчёте по долгам:
  документы и оплаты агрегируются двумя group-by запросами, общий query count
  остаётся равным 3 независимо от количества контрагентов.
- [x] **PERF-06:** hard limit кассовой книги устранён: новый endpoint возвращает
  страницу в обратной хронологии, точный `total`, текущий остаток и корректные
  opening/closing balances; накопительный остаток не сбрасывается между страницами.
  Legacy endpoint сохранён без прежнего ограничения в 1000 строк. Регрессия
  подтверждена отдельным тестом перехода между страницами.
- [x] **PERF-07:** PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` снят на изолированной
  синтетической базе (до 100 тыс. основных записей и 300 тыс. строк документов).
  Зафиксированы планы, времена и узкие места каталога, документов, долгов,
  Dashboard, склада и кассы (`performance-baseline-2026-10-11.md`).
- [x] **PERF-08:** добавлена отдельная migration `0017_performance_indexes` с
  B-tree/composite/GIN trigram индексами; document search переписан с
  cross-table `OR` на объединение индексируемых выборок. Повторный профиль дал
  ускорение ключевых запросов примерно в 8–68 раз, кассовой deep page — в 3,9 раза.
  Цикл downgrade/upgrade и полный backend regression прошли.
- [x] **PERF-09:** выполнен воспроизводимый endpoint-level concurrent load test
  на синтетическом рабочем объёме (`load-test-baseline-2026-10-11.md`): 480
  обычных запросов при concurrency 12 и 80 отчётов при concurrency 4, ошибок 0%.
  Перед production требуется повтор через staging nginx/TLS.
- [x] **PERF-10:** обычные операции укладываются в 2 секунды: общий p95 `580 мс`,
  худший сценарий Dashboard p95 `638 мс`.
- [x] **PERF-11:** stock-balances переведён на server-side pagination
  (`rows + total + offset + limit`) с отдельным SQL aggregate для полной суммы;
  полный export сохранён. На повторном прогоне ответ страницы из 25 строк дал
  p95 `545 мс`, общий p95 отчётов снизился с `5,51 с` до `1,41 с` и прошёл SLO
  5 секунд при 0% ошибок. Перед production остаётся повтор через staging nginx/TLS.

## 4. CI/CD и staging — P0/P1

Ответственные: DevOps, Fullstack, QA.
Оценка: 3–5 рабочих дней.

### CI

- [x] Существуют jobs backend, frontend, PostgreSQL integrity и real E2E.
- [x] Подготовлено отдельное ТЗ на PR/release/staging/production/rollback pipeline (`ci-cd-technical-spec.md`).
- [x] **CICD-00 / P0:** Docker включён; изолированный real E2E-контур поднял
  чистый PostgreSQL, применил миграции до `0018`, выполнил seed и завершил
  `8 passed`. LOG-01 обновлён под обязательную смену временного пароля и
  token revocation. Контейнеры, сеть и tmpfs-volume удалены teardown-процедурой.
- [x] **CICD-01 / P1:** добавлены Ruff lint/format и строгий mypy gate.
  Локально Ruff green; mypy проверяет все 77 source files без ошибок и без
  module allowlist/`ignore_errors`. Исходный gradual allowlist из 13 модулей закрыт.
- [x] **CICD-02 / P1:** добавлен branch coverage gate `82.5%`; локальный baseline
  `196 passed, 4 skipped`, `82.55%`. JUnit и coverage XML сохраняются artifacts.
- [x] **CICD-03 / P0:** PostgreSQL job запускает не только concurrency, но и
  критическое учётное ядро. Локально на чистой временной БД после `0013 -> head`
  прошли `4` теста: уникальная нумерация, конкурентная продажа последнего
  остатка, атомарность stock ledger/неуспешной продажи и частичная оплата со
  сверкой allocation, долга и кассы.
- [x] **CICD-04 / P0:** `alembic check` и upgrade from previous release добавлены
  в workflow. Миграция `0018_reconcile_model_schema` безопасно устраняет
  nullability/index drift, сохраняя существующие unique constraints. Проверены
  наполненный цикл `0018 -> 0017 -> 0018` и чистый PostgreSQL upgrade
  `0013_manager_cash_permissions -> head`; оба завершаются зелёным
  `No new upgrade operations detected`. Первый GitHub Actions run ещё требуется.
- [x] **CICD-05 / P0:** CI real-E2E job собирает backend/frontend из
  `Dockerfile.prod` без bind mounts. Локально получены exact images;
  backend image запускается от пользователя `app`. Первый GitHub Actions run
  нового job ещё требуется.
- [x] **CICD-06 / P0:** real E2E запускается через production nginx/backend
  images и чистый PostgreSQL: one-shot Alembic migration, one-shot E2E seed,
  readiness checks и `8 passed`. Все API-запросы браузера идут через nginx;
  teardown удаляет контейнеры, сеть и tmpfs DB.
- [x] **CICD-07 / P1:** добавлены dependency review, `pip-audit`, production
  `npm audit`, CodeQL и Trivy secret/misconfiguration/container gates. Локально:
  Python lock — 0 известных уязвимостей; production npm tree — 0; оба production
  image — 0 HIGH/CRITICAL. Backend/frontend работают как `app`/`nginx`.
  Первый GitHub Actions run ещё требуется. В полном frontend dev tree остаются
  7 findings (`2 moderate`, `5 high`) в Tailwind 3 build chain; это отдельный
  upgrade/risk-acceptance item, production dependencies не затронуты.
- [x] **CICD-08 / P1:** workflow генерирует SPDX JSON SBOM для backend/frontend
  через Syft и сохраняет их на 30 дней; локальная генерация обоих SBOM прошла.
- [x] **CICD-09 / P1:** base images Python, Node, nginx и PostgreSQL закреплены
  digest'ами; Python dependencies разделены на runtime/dev input и точные lock
  files. Hash-lock для wheels отложен до появления контролируемого package mirror.
- [x] **CICD-10 / P1:** JUnit, оба Playwright HTML-report, dependency/Trivy
  reports и SBOM сохраняются как CI artifacts на 30 дней. Проверка фактических
  artifacts первого GitHub Actions run остаётся release evidence, а не кодовым
  блокером реализации.

### CD и staging

- [x] **CICD-11 / P0:** выбран GHCR рядом с GitHub repository; публикация
  выполняется отдельным manual release workflow с `packages: write`.
- [x] **CICD-12 / P0:** release workflow принимает только полный SHA из `main`,
  для которого существует успешный CI push-run, версию `vX.Y.Z-rc.N`, собирает
  каждый image один раз и публикует теги version и `sha-<full-sha>`; тег `latest`
  не создаётся.
- [x] **CICD-13 / P0:** после push workflow получает registry digest обоих
  images и сохраняет JSON release manifest с SHA, digest-ссылками, Alembic head,
  actor, timestamp, CI/release run URL на 90 дней. Первый реальный publish ещё
  требуется.
- [ ] **CICD-14 / P0:** подготовить staging, повторяющий production topology.
  Image-only Compose и runner contract готовы; нужны реальный host/DNS/TLS,
  self-hosted runner `buy-modern-staging` и environment secrets.
- [ ] **CICD-15 / P0:** автоматически деплоить RC digest в staging. Workflow
  реализован с digest validation, pull без build, migration/readiness/login/
  dashboard smoke и 365-day evidence; первый реальный run ещё не выполнен.
- [x] **CICD-16 / P0:** Alembic выполняется отдельным one-shot `migrate`
  service; backend стартует только после `service_completed_successfully`.
- [ ] **CICD-17 / P0:** добавить protected production environment и manual
  approval. Workflow привязан к environment `production`; остаётся настроить
  required reviewers/защиту в GitHub и выполнить первый approval.
- [ ] **CICD-18 / P0:** production получает staging-tested digest без rebuild.
  Promotion job использует те же outputs publish после успешного staging и не
  содержит build; остаётся реальный deployment run.
- [x] **CICD-19 / P1:** отдельный protected rollback workflow принимает только
  предыдущие digest-ссылки, до переключения проверяет совместимость schema,
  не запускает migration/downgrade, выполняет smoke и сохраняет evidence.

## 5. Backup, restore и observability — P0/P1

Ответственные: DevOps, QA.
Оценка: 2–4 рабочих дня.

### Backup/restore

- [x] Созданы первичные backup/restore scripts.
- [x] **DR-01 / P0:** передавать `--env-file .env.production`.
- [x] **DR-02 / P0:** проверять `$LASTEXITCODE` в PowerShell.
- [x] **DR-03 / P0:** писать dump атомарно через временный файл.
- [x] **DR-04 / P0:** добавить `backups/` и `*.dump` в `.gitignore`.
- [x] **DR-05 / P0:** рассчитывать SHA-256 checksum.
- [x] **DR-06 / P0:** выполнять `pg_restore --list` после backup.
- [ ] **DR-07 / P1:** почасовой systemd timer и scoped 14-day retention
  реализованы и протестированы; остаётся установка/enable на production host.
- [ ] **DR-08 / P1:** настроить шифрованную offsite-копию. Restic client-side
  encryption, validated dump selection, systemd step, metrics/alerts и тесты
  реализованы; real repository, credentials, object lock и restore drill pending.
- [x] **DR-09 / P1:** добавлены метрики последней попытки/success timestamp и
  alerts на failed, stale >75 минут и missing metric; rules прошли `promtool`.
- [x] **DR-10 / P0:** backup восстановлен в отдельную локальную БД; исходная БД
  не изменялась, schema revision и контрольные totals совпали.
- [x] **DR-11 / P0:** на восстановленной копии пройдены readiness `200`, login,
  dashboard smoke и сверка counts/финансовых сумм. Evidence:
  `restore-drill-2026-10-12.md`.
- [ ] **DR-12 / P0:** измерить и утвердить RPO/RTO.

Стартовая цель: `RPO <= 1 час`, `RTO <= 2 часа`.

### Observability

- [x] **OBS-01 / P1:** application/request logs структурированы как JSON в
  production; стандартный Uvicorn access log отключён.
- [x] **OBS-02 / P1:** безопасный входящий или сгенерированный `X-Request-ID`
  возвращается клиенту и включается в request log.
- [x] **OBS-03 / P1:** внутренний Prometheus endpoint экспортирует request
  count/status, active requests, latency histogram и SQLAlchemy pool gauges;
  route labels нормализованы по шаблону, `/metrics` не проксируется nginx.
- [ ] **OBS-04 / P1:** error tracking. Интеграция Sentry и privacy scrubber
  реализованы и покрыты тестами; остаются production DSN и staging event smoke.
- [ ] **OBS-05 / P1:** dashboards для API, БД, disk и backup age. Grafana JSON
  подготовлен; остаются импорт, datasource, node exporter и live-проверка.
- [ ] **OBS-06 / P1:** alerts и проверенные каналы оповещения. Шесть Prometheus
  rules прошли `promtool`; остаются Alertmanager receiver и delivery/recovery drill.
- [x] **OBS-07 / P1:** в production Compose заданы CPU/memory/PID limits и
  `json-file` rotation (`10m x 5`, значения параметризуются env).
- [x] **OBS-08 / P1:** request logger использует allowlist полей; query string,
  body и authorization не записываются. Runtime smoke подтвердил отсутствие
  уникального query marker в логах.

## 6. UAT и генеральная репетиция — P0

Ответственные: QA, Project, бизнес-оператор; Fullstack/DevOps on-call.
Оценка: 2–3 рабочих дня.

- [ ] **UAT-01:** M01 — роли и доступ менеджера.
- [ ] **UAT-02:** M02 — валютный приход и пересмотр цены.
- [ ] **UAT-03:** M03 — продажа, склад, долг и отчёт.
- [ ] **UAT-04:** M04 — отказ расхода при нехватке остатка.
- [ ] **UAT-05:** M05 — перемещение между складами.
- [ ] **UAT-06:** M06 — частичная оплата покупателя.
- [ ] **UAT-07:** M07 — оплата поставщику и переплата.
- [ ] **UAT-08:** M08 — исправление проведённого документа.
- [ ] **UAT-09:** M09 — import/export/PDF/print.
- [ ] **UAT-10:** M10 — полный рабочий день менеджера.
- [ ] **UAT-11:** LOG-01 — логист и складской scope.
- [ ] **UAT-12:** права admin/manager/cashier/viewer/logist.
- [ ] **UAT-13:** readiness становится `503` при отключении БД.
- [ ] **UAT-14:** backup/restore rehearsal.
- [ ] **UAT-15:** application rollback rehearsal.
- [ ] **UAT-16:** сверка товаров, остатков, долгов и кассы.
- [ ] **UAT-17:** подписан UAT protocol.
- [ ] **UAT-18:** подписано GO/NO-GO решение.

## 7. Cutover и hypercare — P0

Ответственные: Project — decision owner; DevOps — deploy owner; Fullstack и QA — on-call.

### До переключения

- [ ] **CUT-01:** подтверждены окно и участники cutover.
- [ ] **CUT-02:** разослано уведомление пользователям.
- [ ] **CUT-03:** legacy write freeze включён.
- [ ] **CUT-04:** получен финальный export/cutoff.
- [ ] **CUT-05:** создан и проверен pre-deploy backup.
- [ ] **CUT-06:** заполнен release record.

### Переключение

- [ ] **CUT-07:** выполнен one-shot migration job.
- [ ] **CUT-08:** выполнен финальный import.
- [ ] **CUT-09:** reconciliation не содержит необъяснённых расхождений.
- [ ] **CUT-10:** deployed утверждённый image digest.
- [ ] **CUT-11:** пройдены technical smoke tests.
- [ ] **CUT-12:** пройдена business acceptance.
- [ ] **CUT-13:** принято явное решение GO или ROLLBACK.

### После запуска

- [ ] **CUT-14:** усиленный мониторинг первые 60 минут.
- [ ] **CUT-15:** daily reconciliation первую неделю.
- [ ] **CUT-16:** incident contacts доступны пользователям.
- [ ] **CUT-17:** завершён hypercare review.
- [ ] **CUT-18:** проведена release retrospective.

## Финальный production release gate

Все пункты ниже должны быть отмечены перед production GO:

- [x] Чистый RC SHA/tag: `v0.1.0-rc.1` / `8dd7ff0c8135853dc56ca99e7e06a15fa06ea3e6`.
- [x] Все обязательные CI checks green на RC SHA: [CI #13](https://github.com/EgorArutiunean/faethon-system/actions/runs/38375823933).
- [x] Real E2E и exact production smoke green на чистом RC SHA; registry
  manifest сохранён в [release run #1](https://github.com/EgorArutiunean/faethon-system/actions/runs/38378201594).
- [ ] Открытых P0 нет.
- [ ] P1 закрыты либо оформлено письменное risk acceptance.
- [ ] Legacy import и reconciliation подписаны.
- [ ] Demo credentials отсутствуют.
- [ ] HTTPS, secrets, CORS и readiness проверены.
- [ ] Backup восстановлен в отдельной среде.
- [ ] RPO/RTO подтверждены измерением.
- [ ] Staging использует те же image digests.
- [ ] UAT подписан бизнесом.
- [ ] Rollback отрепетирован.
- [ ] Project owner дал явное разрешение на production GO.

## Журнал обновлений

| Дата | Изменение | Автор / ссылка |
|---|---|---|
| 2026-10-10 | Создан living checklist по результатам повторного аудита | Codex |
| 2026-10-10 | Catalog hardening: recursive tree, price-control, cycle guard, RU/EN i18n; backend `168 passed, 2 skipped`, frontend build passed, Playwright `4 passed` | Working tree, commit pending |
| 2026-10-10 | Backup artifacts `backups/` и `*.dump` исключены из Git | Working tree, commit pending |
| 2026-10-11 | Production auth/config hardening, one-time admin bootstrap и DB/schema readiness; backend `176 passed, 2 skipped`, frontend typecheck/build и Playwright `4 passed` | Working tree, commit pending |
| 2026-10-11 | Backup/restore scripts hardened: production env-file, atomic dump, exit-code checks, checksum и `pg_restore --list`; PowerShell parse и Compose config пройдены | Runtime restore drill pending |
| 2026-10-11 | Документация согласована с catalog-only legacy scope и текущим NO-GO; удалены устаревший force-push workflow, локальные пути/hostname и literal legacy password | Working tree, commit pending |
| 2026-10-11 | Все modified/untracked файлы классифицированы; зафиксирован commit split и явный exclude для GDB/XLSX/secrets/backups | `release-change-inventory-2026-10-11.md` |
| 2026-10-11 | CI усилен проверкой upgrade предыдущего release head `0013 -> head`, `alembic check` и обязательным сохранением JUnit/Playwright evidence | `.github/workflows/ci.yml` |
| 2026-10-11 | Повторная локальная регрессия после SEC-06: backend `178 passed, 2 skipped`; frontend typecheck/build; mock Playwright `5 passed`; CI YAML parse | PostgreSQL/real E2E blocked: Docker daemon off |
| 2026-10-11 | Подготовлено отдельное ТЗ на CI/CD: immutable images, staging promotion, approvals, migrations, rollback, evidence и acceptance criteria | `ci-cd-technical-spec.md` |
| 2026-10-11 | SEC-06: bootstrap/admin-reset passwords помечаются временными; API блокирует рабочие permissions до self-service смены; добавлены migration, UI и E2E | Targeted backend `33 passed`; mock Playwright `5 passed` |
| 2026-10-11 | SEC-10: persistent login lockout с настраиваемыми threshold/cooldown, row lock и сбросом после success/password reset | Backend `179 passed, 2 skipped`; production Compose config passed |
| 2026-10-11 | SEC-11: access-only JWT TTL <= 60 минут и server-side revocation при logout/password change/admin reset | Backend `181 passed, 2 skipped`; frontend build; mock Playwright `5 passed` |
| 2026-10-11 | SEC-12: streaming body cap, row cap и XLSX ZIP-bomb/format safeguards; nginx limit синхронизирован | Import `15 passed`; backend `185 passed, 2 skipped`; production Compose config passed |
| 2026-10-11 | SEC-13 частично: добавлены HSTS, CSP, frame/referrer/permissions/opener headers; TLS и внешний HTTPS smoke остаются infrastructure blocker | `frontend/nginx.conf` |
| 2026-10-11 | CICD-04: ORM/migration drift закрыт миграцией `0018`; наполненный downgrade/upgrade, чистый `0013 -> head`, `alembic check` и backend `193 passed, 2 skipped` прошли | Working tree, commit pending |
| 2026-10-11 | CICD-00: real browser E2E на чистом PostgreSQL и текущей head `0018` повторён; все M02–M08 и LOG-01 прошли, изолированный Compose-контур удалён | Playwright `8 passed` |
| 2026-10-11 | CICD-03: PostgreSQL CI matrix расширена критическим accounting core; чистый `0013 -> head`, schema check и четыре concurrency/accounting теста прошли | PostgreSQL `4 passed`; SQLite `193 passed, 4 skipped` |
| 2026-10-12 | CICD-05/06: CI переведён на exact production Docker images; локальный production-контур выполнил migration, seed, readiness и все M02–M08/LOG-01 через nginx; найден и исправлен race при редактировании строки корректировки | Playwright production/PostgreSQL `8 passed`; teardown clean |
| 2026-10-12 | CICD-07..10: добавлены supply-chain gates, CodeQL, dependency review/audits, Trivy, SPDX SBOM и 30-дневные evidence artifacts; actions и base images закреплены SHA/digest, Python runtime/dev locks разделены, оба production-контейнера non-root | Backend `193 passed, 4 skipped`; production E2E `8 passed`; Python/npm production/image scans — 0; Syft SBOM — 2 generated; first GitHub run pending |
| 2026-10-12 | CICD-11..13: выбран GHCR; добавлен ручной RC workflow с валидацией version/full main SHA, однократной сборкой, immutable version/SHA tags и JSON manifest фактических registry digest'ов | `.github/workflows/release.yml`; first publish pending |
| 2026-10-12 | CICD-01/02: backend приведён к Ruff format, добавлены lint/format/gradual-mypy gates и branch coverage threshold 82.5%; coverage XML включён в evidence | Ruff green; mypy `77 source files`; pytest `193 passed, 4 skipped`; branch coverage `82.5%` |
| 2026-10-12 | Gradual typing debt сокращён: исправлены конфликт имени FastAPI app, ORM date annotation, dashboard serialization, export/report typing и dynamic pricing boundary; mypy allowlist уменьшен с 13 до 4 модулей | Ruff/mypy green; backend `193 passed, 4 skipped`; readiness/login `200` |
| 2026-10-12 | Gradual typing debt закрыт полностью: типизированы auth dependency, payment invariants, dialect-specific document numbering, repost candidate и warehouse movement keys; module allowlist удалён | Ruff green; mypy `77 source files` без исключений; backend `196 passed, 4 skipped`; branch coverage `82.55%` |
| 2026-10-12 | DR-10/11: PowerShell quoting defect найден и исправлен; custom dump с checksum восстановлен в отдельную БД, контрольные counts/sums совпали, readiness/login/dashboard smoke прошли | Restore `1.03 s`; `restore-drill-2026-10-12.md`; staging RPO/RTO approval pending |
| 2026-10-12 | OBS-01/02/07/08: добавлены JSON request logs, `X-Request-ID`, safe field allowlist, отключение query-bearing Uvicorn access log, Docker rotation и resource limits | Ruff/mypy green; backend `200 passed, 4 skipped`; branch coverage `82.72%`; runtime request-id/query-redaction smoke passed |
| 2026-10-12 | OBS-03: добавлен внутренний Prometheus endpoint с HTTP counters/status, latency histogram, active requests и SQLAlchemy pool gauges; публичный nginx его не проксирует | Ruff/mypy green; backend `202 passed, 4 skipped`; branch coverage `82.98%`; runtime metrics smoke passed |
| 2026-10-12 | OBS-04/05/06 implementation: добавлены Sentry с PII/request scrubber, release/environment и request-id; Prometheus scrape + 6 alert rules; Grafana overview; backup freshness metric и runbook | Ruff/mypy green; backend `205 passed, 4 skipped`; branch coverage `83.1%`; targeted `9 passed`; YAML/JSON/shell/PowerShell syntax valid; `promtool` config/rules passed; external DSN/dashboard/receiver drills pending |
| 2026-10-12 | CICD-16: production Compose получил one-shot Alembic migration service и блокировку старта backend до успешного upgrade | Изолированный clean PostgreSQL прошёл `empty -> 0018`; startup chain `postgres -> migrate -> backend` завершился readiness `200` на revision `0018`; временный volume удалён |
| 2026-10-12 | CICD-14/15 implementation: добавлены image-only release Compose, staging job на protected Environment/self-hosted runner, immutable digest validation, schema check, external authenticated smoke и `staging-passed` evidence | actionlint green для всех workflows; image-only clean-stack smoke прошёл migration `0018` и nginx readiness `200`; backend `206 passed, 4 skipped`, coverage `83.1%`; real staging host/runner/secrets/TLS/run pending |
| 2026-10-13 | CICD-17/18 implementation + CICD-19: production promotion требует successful staging, environment approval, UAT/backup/rollback refs и использует те же digest'ы; добавлен application-only rollback workflow | actionlint green; локальный rollback drill подтвердил schema `0018`, отсутствие повторного migration и readiness `200`; GitHub environment protection и реальные staging/production runs pending |
| 2026-10-13 | DR-07 implementation + DR-09: backup получил project-label discovery без CD env/secrets, 14-day scoped retention, success/failure metrics, hourly systemd unit/timer и failed/stale/missing alerts | Shell retention/failure tests `2 passed`; полный backend regression `208 passed, 4 skipped`, coverage `83.1%`; PowerShell/shell syntax green; `promtool` подтвердил 7 rules; runtime backup 129908 bytes + checksum + success metric; smoke artifacts удалены; production timer install pending |
| 2026-10-13 | DR-08 implementation: добавлена Restic offsite replication с client-side encryption, повторной SHA-256 validation, least-privilege runbook и отдельными success/failure/freshness metrics | Targeted `4 passed`; полный backend regression `211 passed, 4 skipped`; Ruff/shell syntax green; `promtool` подтвердил 10 rules; real repository/object lock/offsite restore остаются release gate |
| 2026-10-13 | Локальная RC qualification: backend CI gate, migration integrity, frontend build, mock и production-like E2E, workflow/Compose validation, secret/misconfiguration/dependency/image scans | Backend `211 passed, 4 skipped`, branch coverage `83.05%`; PostgreSQL `4 passed`; Playwright `5 + 8 passed`; Trivy HIGH/CRITICAL `0`; immutable local image manifest создаётся после фиксации commits |
| 2026-10-13 | Clean digest smoke обнаружил отсутствие ORM registry import в standalone admin bootstrap; добавлен импорт `app.db.base` и fresh-process regression test | Production security `7 passed`; полный backend gate `211 passed, 4 skipped`, branch coverage `83.05%`; повторный exact-digest smoke прошёл login/password-change/dashboard/readiness |
| 2026-10-13 | Опубликован RC `v0.1.0-rc.1` на SHA `8dd7ff0c8135853dc56ca99e7e06a15fa06ea3e6`; два push-CI завершились успешно; release workflow собрал GHCR images и artifact manifest | Backend `sha256:cd7e6c99b913c1e37e2f5fb06b05c5e819f049b272bc59c5a139ff6fe4a55df2`; frontend `sha256:25cf239c6660f17a28ec4011aab44a12d66ec5de79259ae4ced3b8aefb21d795`; staging job queued до подключения runner `buy-modern-staging` |
