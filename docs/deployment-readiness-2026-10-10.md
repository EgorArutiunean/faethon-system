# Buy Modern: текущее состояние и план подготовки к деплою

Дата аудита: 2026-10-10
Аудируемая ветка: `main`
Исходный `HEAD` аудита: `9ba3c20`
Решение на дату аудита: **GO для демо и UAT; NO-GO для production с реальными финансовыми данными**.

Обновление 2026-10-13: локальный backup/restore drill завершён; внутренние
Prometheus metrics, Sentry integration, alert rules и Grafana dashboard
реализованы. Решение остаётся **NO-GO**, пока не подключены внешний HTTPS,
staging, offsite backup, реальные monitoring receivers и не подписаны UAT/cutover.

Живой трекер выполнения: [deployment-work-plan.md](deployment-work-plan.md).
Подробное ТЗ на delivery pipeline: [ci-cd-technical-spec.md](ci-cd-technical-spec.md).

## 1. Executive summary

Buy Modern — развитый full-stack MVP учётной системы, реализованный как модульный монолит:

- React 19 / TypeScript / Vite SPA;
- FastAPI / SQLAlchemy / Pydantic;
- PostgreSQL 16 и 18 Alembic-миграций;
- nginx и Docker Compose для production;
- pytest, Playwright и GitHub Actions CI.

Основное учётное ядро уже существует: справочники, документы, складской ledger,
платежи и распределения, долги, касса, валюты, логистика, отчёты, экспорт,
печатные формы, импорт, аудит и RBAC.

До production мешает не отсутствие базовой функциональности, а незавершённый
release/operations-контур:

1. текущий release candidate не зафиксирован — рабочее дерево содержит большой
   классифицированный, но ещё не закоммиченный набор изменений;
2. миграция и сверка legacy-данных не завершены;
3. новый production-image job ещё не подтверждён первым GitHub Actions run;
4. registry, immutable promotion, CD и staging отсутствуют;
5. локальная restore-репетиция пройдена, но нет offsite-копии и утверждённого
   staging RPO/RTO;
6. observability-код и конфигурации подготовлены, но нет live Sentry,
   Prometheus/Grafana/Alertmanager, проверенного канала alerts и внешнего TLS.

Оценка готовности:

| Контур | Готовность | Решение |
|---|---:|---|
| Портфолио / демонстрация | 85% | GO после очистки demo-данных |
| Функциональный MVP | 75–80% | GO для UAT |
| Контролируемый staging / pilot | 55–60% | GO после P0 hardening |
| Production cutover | 40–45% | NO-GO |

## 2. Что реализовано

### Платформа и архитектура

- API разделён на `routes -> schemas -> services -> models`.
- Подключено 15 функциональных router-модулей в `backend/app/main.py`.
- В коде 86 HTTP endpoints.
- Alembic имеет одну голову: `0018_reconcile_model_schema`; локально проверены
  upgrade `0013 -> head`, downgrade/upgrade последней миграции и `alembic check`.
- Production topology: nginx/frontend -> FastAPI -> PostgreSQL.
- Backend production container работает от непривилегированного пользователя.
- PostgreSQL не публикуется наружу в production Compose.

### Бизнес-функции

- товары, группы товаров, контрагенты и склады;
- приход, расход, корректировка и перемещение;
- черновик, проведение, отмена и контролируемое перепроведение документа;
- последовательная нумерация, ревизии и audit trail;
- остатки и движения с блокировками от конкурентных изменений;
- платежи, ручное распределение по документам, авансы и частичные оплаты;
- долги и выписки контрагентов;
- единая касса, кассовая книга и запрет отрицательного остатка;
- валюты и фиксация курса во входящих документах;
- складские задания и ограничение логиста назначенными складами;
- отчёты, CSV/XLSX, HTML/PDF;
- Import Lite и dry-run;
- пользователи, роли, разрешения и складской scope.

### Сильные инженерные решения

- денежные расчёты используют `Decimal`;
- присутствуют database constraints и unique constraints;
- применяются row locks и отдельная блокировка кассы;
- ревизии проведённых документов сохраняют историю изменений;
- есть тесты конкурентного проведения в PostgreSQL;
- CI разделён на backend, frontend, PostgreSQL integrity и real E2E jobs.

## 3. Результаты проверки 2026-10-10

| Проверка | Результат |
|---|---|
| Backend pytest | SQLite matrix: `196 passed, 4 skipped`; PostgreSQL matrix: `4 passed` |
| Backend quality | Ruff lint/format green; mypy green for all 77 source files with no module allowlist or `ignore_errors` |
| Backend branch coverage | `82.55%`; CI rejects regression below `82.5%` and stores coverage XML |
| Причина skip | четыре PostgreSQL-only concurrency/accounting теста выполняются отдельным job |

Последний полный backend regression после staging delivery hardening
(2026-10-13): `210 passed, 4 skipped`; последний coverage-прогон `83.1%`; Ruff и mypy
прошли. Шесть Prometheus rules проверены официальным `promtool`; image-only
clean-stack smoke дошёл до migration `0018` и nginx readiness `200`.
| Frontend TypeScript | passed |
| Frontend production build | passed |
| Mock Playwright | актуальный прогон: `5 passed` |
| Real PostgreSQL E2E | актуальный изолированный прогон: `8 passed` на head `0018` |
| Exact production-image E2E | `8 passed` через production nginx/backend images и чистый PostgreSQL; teardown clean |
| Supply-chain scans | Python dev lock: 0; npm production dependencies: 0; backend/frontend images: 0 HIGH/CRITICAL |
| SBOM | SPDX JSON успешно сгенерирован локально для обоих production images |
| Container users | backend: `app`; frontend: `nginx` |
| E2E в исходниках | 5 mock + 8 real scenarios |
| Production Compose parse | passed с тестовыми env values |
| Alembic | одна голова `0018`; `0013 -> head` и `alembic check` прошли |
| Git baseline | `HEAD == origin/main`; release diff классифицирован, но working tree ещё не зафиксирован как RC |

Эти результаты нельзя считать финальным release evidence: production-image
проверка выполнена на текущем working tree, но весь набор должен быть повторён
и сохранён CI на одном чистом RC SHA.

## 4. Текущие риски

### P0 — блокирует production

#### 4.1. Нет воспроизводимого release candidate

Текущий release diff классифицирован, а каталог переведён на bounded server-side
pagination/search/sort с отдельными lookup endpoints. Price-control UX,
косвенные циклы категорий, вложенные группы и i18n закрыты кодом и тестами.
Незакрытый риск — большой working tree ещё не разбит на reviewable commits и не
зафиксирован чистым RC SHA/tag.

До RC необходимо:

- разбить классифицированный diff на reviewable commits;
- провести review и полный обязательный CI на одном SHA;
- зафиксировать чистый commit и RC tag.

#### 4.2. Legacy migration не закрыта

По `BUY.GDB` уже подтверждены InterBase 7.1 / ODS 11.1, 68 relations и отсутствие
bad pages. Просмотрены как минимум:

- `STOVAR` — товары;
- `SGRP` — группы;
- `SEDIZM` — единицы измерения;
- `LICO` — содержит персональные и паспортные данные.

Нужен минимизированный read-only export справочников. Полный `LICO` экспортировать
нельзя. Источники начальных остатков, долгов и кассы пока не подтверждены.

Критическое продуктовое решение:

- если доступны только справочники — выпускать сначала **catalog/demo pilot** без
  заявления о корректном финансовом cutover;
- для полноценной эксплуатации отдельно получить и подписать cutoff totals по
  складу, долгам и кассе либо согласовать их ручной ввод на дату перехода.

#### 4.3. Production identity hardening — закрыто локально

Production запрещает demo seed и слабый secret, использует one-time bootstrap
администратора и обязательную смену временного пароля. Demo hint отсутствует в
production build; сценарий проверен backend-тестами и Playwright.

#### 4.4. Liveness/readiness — закрыто локально

Разделены `/health/live` и DB/schema-aware `/health/ready`; неготовая БД или
revision дают `503`, Compose использует readiness. Это подтверждено тестами и
production-image E2E.

#### 4.5. Backup/restore не доказаны

Скрипты уже используют production env-file, проверяют коды завершения, создают
checksum и валидируют dump; backup artifacts исключены из Git. Локальный restore
drill на отдельной БД пройден 2026-10-12 с совпадением контрольных сумм,
readiness/login/dashboard smoke. Остаются staging rerun, retention/offsite policy
и утверждение RPO/RTO.

#### 4.6. Нет CD и проверки точных production artifacts

CI и локальный harness теперь собирают `Dockerfile.prod` и выполняют все восемь
real E2E через production nginx/backend images. Оба контейнера запускаются
non-root; dependency/SAST/container gates и SBOM реализованы. Остаются первый
подтверждённый GitHub Actions run, registry, immutable release tags/digests,
staging, approval и release record.

### P1 — закрыть до промышленной эксплуатации

- server-side pagination/search и ответы вида `items + total` для остальных крупных
  списков (основные реестры товаров, документов и контрагентов закрыты в
  `PERF-01..03`; кассовая книга закрыта в `PERF-06`; payments и специализированные
  списки оцениваются отдельно);
- подтвердить PostgreSQL-план и SLO paged кассовой книги (`PERF-06` устранил
  hard limit и сохраняет сквозной накопительный остаток; baseline снят в
  `PERF-07`, индексы закрыты в `PERF-08`, локальный endpoint SLO проходит в
  `PERF-09/10`; требуется повтор на staging);
- подтвердить PostgreSQL-план и SLO реализованного aggregate endpoint Dashboard
  (`PERF-04` закрыт функционально, baseline и индексы закрыты в `PERF-07/08`,
  локальный endpoint SLO проходит в `PERF-09/10`; требуется повтор на staging);
- подтвердить планы и время агрегированных запросов долгов на PostgreSQL
  (`PERF-05` устранил N+1 функционально; baseline `EXPLAIN ANALYZE` снят в
  `PERF-07`, индексы и повторный замер закрыты в `PERF-08`, локальный load/SLO
  проходит в `PERF-09/10`; требуется повтор на staging);
- повторить на staging пагинированный stock-balances report: локально `PERF-11`
  закрыт, p95 страницы из 25 строк снизился с `5,73 с` до `545 мс`, общий p95
  отчётов — до `1,41 с` при 0% ошибок;
- лимиты и streaming для больших import/export;
- JSON logs, request ID и внутренние HTTP/DB-pool metrics реализованы; остаются
  error tracking, monitoring storage/dashboards и alerts;
- TLS, HSTS, CSP и точный HTTPS CORS origin;
- login rate limiting / lockout;
- проверенная библиотека JWT, сокращение TTL или refresh/revocation policy;
- wheel hash-lock после подключения контролируемого package mirror; exact-version
  runtime/dev locks и digest pinning base images уже реализованы;
- обновление Tailwind 3 build chain либо формальное risk acceptance для 7
  dev-only npm findings; production npm tree локально чист;
- Ruff/format, full-project mypy без исключений и branch coverage 82.5% уже
  являются CI gates;
- ESLint и component tests для UI;
- раздельные PostgreSQL users для migration и runtime;
- resource limits и Docker log rotation реализованы в production Compose.

### P2 — после первого стабильного релиза

- accessibility и Firefox/WebKit smoke;
- gzip/brotli и immutable frontend cache;
- read-only filesystem, `cap_drop`, `no-new-privileges`;
- canary/blue-green;
- API compatibility и chaos tests.

## 5. Рекомендуемая стратегия: два независимых трека

### Трек A — публичное portfolio demo

Цель: показать функциональность без legacy PII и финансового риска.

- отдельный `demo` environment и база;
- синтетические товары, партнёры, склады и документы;
- автоматический reset demo-базы по расписанию;
- read-only viewer либо ограниченные demo roles;
- watermark «Демонстрационная среда»;
- запрет выгрузки реальных legacy-файлов;
- rate limiting и ограничение ресурсов;
- публичная landing page с тестовыми сценариями M01–M08.

Оценка: 2–4 рабочих дня после стабилизации текущего WIP.

### Трек B — внутренний production

Цель: реальная работа компании с контролируемым переносом данных.

Требует всех P0, staging rehearsal, reconciliation и подписанного GO/NO-GO.
Оценка: 3–5 недель, причём критический путь зависит от источников остатков,
долгов и кассы.

## 6. План подготовки к production

### Этап 0. Зафиксировать baseline — 1–2 дня

Ответственные: Fullstack + QA + Project.

- Разбить классифицированный release diff на reviewable commits.
- Провести review уже реализованных catalog/price-control изменений.
- Повторить обязательную матрицу на одном чистом SHA.
- Получить чистый `main` и создать `rc/0.1.0` tag.
- Зафиксировать scope: что входит и что явно не входит в релиз.

Результат: один воспроизводимый SHA, changelog и перечень accepted limitations.

### Этап 1. Security и runtime hardening — 3–5 дней

Ответственные: Fullstack + DevOps + QA.

- Ввести `APP_ENV` и fail-fast validation production config.
- Убрать demo credentials и внедрить one-time admin bootstrap.
- Реализовать liveness/readiness.
- Добавить rate limiting login.
- Настроить HTTPS, HSTS/CSP и точный CORS.
- Добавить import limits и защиту XLSX processing.

Результат: production не стартует с placeholder secrets, HTTP origin или demo seed.

### Этап 2. Legacy export и migration rehearsal — 5–10 дней

Ответственные: Fullstack/Data + Project + оператор + QA.

- Экспортировать только необходимые поля `STOVAR`, `SGRP`, `SEDIZM`.
- Исключить паспортные и другие лишние данные `LICO`.
- Добавить units, staging tables, batch ID, idempotency и bulk upsert.
- Исправить mapping учётной/розничной цены.
- Выполнить dry-run и apply в чистую staging DB.
- Сверить counts, суммы, дубликаты и исключения.
- Зафиксировать источник opening stock/debt/cash либо решение о ручном вводе.

Результат: повторяемый import package и подписанный reconciliation report.

### Этап 3. Производительность и корректность UI/API — 3–6 дней

Ответственные: Fullstack + QA.

- [x] Server-side search/sort/pagination для товаров, документов и контрагентов.
- [x] Permission-aware aggregate API для Dashboard.
- [x] Устранить N+1 queries в partner balances и отчёте по долгам.
- [x] Добавить индексы после PostgreSQL `EXPLAIN ANALYZE`.
- [x] Прогнать 20 000 товаров, 100 000 документов и 300 000 строк документов.
- [x] Зафиксировать и локально подтвердить SLO: обычные операции <= 2 секунд,
  отчёты <= 5 секунд. Повтор через staging nginx/TLS остаётся release gate.

Результат: performance report и отсутствие расчётов по неполному клиентскому slice.

### Этап 4. CI/CD — 3–5 дней

Ответственные: DevOps + Fullstack + QA.

CI для каждого PR:

1. backend lint/typecheck/tests/coverage;
2. полный критический suite на PostgreSQL;
3. Alembic heads/check/upgrade from previous release;
4. frontend typecheck/build/mock tests;
5. build точных production images;
6. поднятие release-compose и real E2E по этим images;
7. secret, dependency, SAST и container scans;
8. SBOM и публикация image digests.

CD:

1. один build для RC, images `version + SHA`;
2. push в registry;
3. auto-deploy тех же digest в staging;
4. one-shot migration job до запуска новой версии;
5. staging smoke/UAT;
6. manual approval production environment;
7. deploy по digest без rebuild на сервере;
8. release record: SHA, digests, Alembic revision, backup ID, test evidence.

### Этап 5. Operations и disaster recovery — 2–4 дня

Ответственные: DevOps + QA.

- Исправить backup/restore scripts и env handling.
- Добавить atomic temp file, checksum и `pg_restore --list`.
- Настроить расписание, retention, шифрование и offsite storage.
- Восстановить backup в отдельную БД и повторить smoke/control reports.
- Добавить JSON logs, request ID, metrics и alerts.
- Настроить disk, DB, 5xx, latency и backup-age monitoring.

Стартовые цели: `RPO <= 1 час`, `RTO <= 2 часа`.

### Этап 6. UAT и генеральная репетиция — 2–3 дня

Ответственные: QA + Project + бизнес-пользователь + Fullstack/DevOps on-call.

- M01–M10 и LOG-01 на staging.
- Полный рабочий день менеджера: приход -> продажа -> оплата -> касса -> отчёты.
- Импорт, экспорт, PDF/печать и права всех ролей.
- Отказ БД должен переводить readiness в `503`.
- Backup/restore и rollback rehearsal.
- Проверка контрольных итогов по товарам, складам, долгам и кассе.

Результат: подписанный UAT и GO/NO-GO protocol.

### Этап 7. Cutover — 1 день + неделя hypercare

Ответственные: Project как decision owner; DevOps как deploy owner; Fullstack и QA.

1. Freeze legacy writes.
2. Финальный export и pre-deploy backup.
3. Migration job и reconciliation.
4. Deploy проверенных image digests.
5. Smoke и business acceptance.
6. Явная точка решения GO/ROLLBACK.
7. Усиленный мониторинг первые 60 минут.
8. Ежедневная сверка ключевых итогов первую неделю.

## 7. Release gates

### Source gate

- [ ] чистое рабочее дерево;
- [ ] RC tag соответствует одному проверенному SHA;
- [ ] branch protection требует CI и review;
- [ ] в Git нет env, GDB, XLSX, dumps, PII и коммерческих экспортов.

### Test gate

- [ ] backend green без неожиданных skip;
- [x] PostgreSQL concurrency и accounting core green локально: `4 passed`;
- [x] TypeScript и production build green локально;
- [x] текущие mock (`5`) и real PostgreSQL E2E (`8`) green;
- [x] smoke/E2E проходит на точных production images локально: `8 passed`;
- [ ] открытых P0/P1 нет либо есть подписанное risk acceptance.

### Data gate

- [x] одна Alembic head и schema diff отсутствует локально;
- [x] upgrade проверен на clean DB от предыдущей release revision `0013`;
- [ ] import повторяем и идемпотентен;
- [ ] counts и контрольные суммы подписаны;
- [ ] политика PII соблюдена.

### Security gate

- [ ] только HTTPS;
- [ ] placeholder/demo secrets отсутствуют;
- [ ] первый admin создан безопасно;
- [ ] Critical/High findings отсутствуют или письменно приняты;
- [ ] наружу доступны только 80/443.

### Backup/operations gate

- [ ] backup имеет checksum и проходит validation;
- [ ] restore выполнен в отдельной среде;
- [ ] RPO/RTO измерены;
- [ ] readiness, dashboards и alerts работают;
- [ ] runbook и контакты incident response доступны.

### Deploy/rollback gate

- [ ] staging и production используют одинаковые image digests;
- [ ] production deploy требует ручного approval;
- [ ] rollback приложения отрепетирован;
- [ ] восстановление БД отрепетировано;
- [ ] release record заполнен.

## 8. Области ответственности

| Роль | Ответственность в этом релизе |
|---|---|
| Fullstack | бизнес-правила, API/UI, migration code, security fixes, performance |
| QA | risk-based plan, API/UI/E2E, regression, migration reconciliation, UAT evidence |
| DevOps | images, registry, CI/CD, secrets, TLS, probes, monitoring, backup/restore, rollout |
| Project | scope, решения по данным, владельцы/сроки, UAT, risk acceptance, GO/NO-GO |
| Бизнес-оператор | проверка legacy semantics, контрольных итогов и реальных сценариев |

## 9. Следующие пять действий

1. Разбить классифицированный diff на reviewable commits и получить чистый RC SHA.
2. Запустить обязательный GitHub Actions matrix и сохранить release evidence.
3. Выбрать registry и реализовать immutable `version + SHA + digest` publication.
4. Создать production-like staging и promotion без rebuild с rollback rehearsal.
5. Завершить scoped legacy export и принять решение по opening balances.

До выполнения этих действий не назначать дату production cutover. Дату можно
назначать после успешных этапов 0–3 и подтверждения источников начальных итогов.
