# Полный технический отчёт по Faethon System / Buy Modern

Дата аудита: 2026-09-04; актуализировано: 2026-10-13
Репозиторий: `buy-modern`, ветка `main`, исходный HEAD аудита `9ba3c20`
Назначение: современная замена legacy-приложения BuySell для складского, товарного, денежного и долгового учёта.

## 1. Executive summary

Проект находится на уровне развитого MVP / release candidate по функциональности, но ещё не готов к безопасному промышленному cutover. Операционное ядро уже покрывает каталог, контрагентов, склады, документы, остатки, платежи, кассу, отчётность, импорт, печать, роли и аудит. Реализованы транзакционные сценарии и защита от части конкурентных конфликтов. Есть Docker-окружения, Alembic, GitHub Actions, mock и real E2E на PostgreSQL.

Главные ограничения релиза лежат не в количестве экранов, а в подтверждении предметной области и эксплуатации: не завершена миграция справочников из `BUY.GDB`, не получены и не сверены отдельные начальные срезы остатков, долгов и кассы, ряд legacy-правил всё ещё открыт, отсутствуют staging/production delivery, наблюдаемость, формальная политика rollback и подтверждённое восстановление резервной копии. История документов и платежей из `BUY.GDB` не мигрируется. До закрытия этих пунктов статус должен быть `NO-GO` для production с реальными финансовыми данными.

Оценка масштаба на дату аудита:

- 49 коммитов в текущей истории, один Git-автор;
- около 9 212 строк Python, 5 975 строк TypeScript/TSX и 3 244 строк проектной документации;
- 93 Python-файла и 30 TS/TSX-файлов в приложении и тестовых наборах;
- 18 последовательных Alembic-миграций, включая performance indexes и reconciliation ORM/schema drift;
- актуальная SQLite-матрица: 193 теста прошли, 4 PostgreSQL-only теста пропущены;
  отдельная PostgreSQL concurrency/accounting matrix: 4 теста прошли;
- 5 mock Playwright-сценариев и 8 успешно повторённых real E2E-сценариев на чистом PostgreSQL/head `0018`;
- 15 групп API: auth, users, products, product groups, partners, warehouses, documents, stock, payments, cash, currencies, reports, imports, audit, logistics.

Важно: на момент аудита рабочее дерево содержит незакоммиченные изменения каталога, API-клиента, CSS и документации. Это WIP, который не следует включать в описание стабильного `main`, пока он не пройдёт review и CI.

## 2. Что уже сделано

### Бизнес-функциональность

- Справочники товаров, иерархических товарных групп, партнёров и складов.
- Типизация партнёров: клиент, поставщик или оба типа, с серверной валидацией допустимых документов и платежей.
- Жизненный цикл документов: черновик, редактирование, строки, проведение, контролируемая коррекция/перепроведение, отмена и защита проведённых данных.
- Приход, расход и перемещение между складами; движения и текущие остатки.
- Непрерывная нумерация с блокировкой последовательности и возможностью разрешённой ручной корректировки.
- Валютный приход: валюта, курс, исходная и базовая суммы, подсказка по пересмотру цены.
- Последняя закупочная стоимость и контроль минимальной наценки 10%.
- Платежи клиента/поставщику, проведение, отмена, ручное распределение по нескольким накладным, частичные оплаты, авансы и переплаты.
- Единая касса первого релиза: приход, расход, корректировка фактического остатка с причиной, запрет отрицательного остатка.
- Балансы и выписки контрагентов.
- Логистические задания с привязкой к складам и состояниями выполнения.
- Реестры документов, складские, долговые и кассовые отчёты; CSV/XLSX-экспорт.
- HTML/PDF-печатная форма расходной накладной с кириллицей.
- Import Lite для CSV/XLSX: товары, партнёры, склады, входящие остатки и начальные долги, включая dry-run.
- RU/EN UI, защищённые маршруты, permission-aware действия, уведомления, таблицы с поиском/сортировкой/пагинацией.

### Инженерные решения

- Слои `API routes -> schemas -> services -> SQLAlchemy models` отделяют HTTP, контракт, бизнес-правила и хранение.
- Для денег и количества используется `Decimal`, а не float.
- Проведение документов и платежей выполняется транзакционно; применяются row locks и PostgreSQL advisory locks для нумерации, остатков, кассы и заданий.
- Остатки представлены как баланс плюс неизменяемые движения, действия фиксируются в audit log.
- Схема развивается миграциями, а не `create_all` в production.
- Real E2E использует изолированный PostgreSQL в `tmpfs`, миграции, seed и настоящий backend.
- Production frontend собирается multi-stage образом и раздаётся nginx; backend запускается непривилегированным пользователем.
- Есть backup/restore-скрипты для PostgreSQL и ручные deployment/smoke-инструкции.

## 3. Архитектура и техническое описание

Система — модульный монолит. Это разумный выбор для текущего размера и домена: учётные операции требуют общей транзакции, а эксплуатационная сложность микросервисов пока не окупается.

Поток запроса:

1. React SPA получает JWT после входа и вызывает REST API `/api/v1`.
2. FastAPI route проверяет пользователя и permission, валидирует Pydantic-схему.
3. Service layer выполняет бизнес-правила и транзакционные изменения.
4. SQLAlchemy пишет в PostgreSQL: мастер-данные, документы, проводки остатков, платежи, кассовые операции, ревизии и аудит.
5. Отчёты читают операционные регистры и отдают экранный результат или экспорт.
6. В production nginx обслуживает SPA и проксирует `/api` и `/health` на backend.

Ключевые доменные агрегаты:

- Identity: user, role, permission, user-warehouse assignment.
- Catalog: product, product group, price/cost attributes.
- Parties: partner и его customer/supplier capabilities.
- Documents: header, lines, number sequence, revisions и status machine.
- Stock: warehouse, balance и movement ledger.
- Finance: payment, allocation, cash operation и вычисляемые partner/cash balances.
- Logistics: warehouse task, assignment, execution state and history.
- Operations: audit event, import job/result, report/export/print representations.

Архитектурно важный инвариант: изменение проведённого документа должно сохранять историю, атомарно отменять старый эффект и применять новый; продажа не должна увести склад в минус; кассовая операция не должна продублироваться при перераспределении платежа.

## 4. Использованные технологии и навыки

### Backend

- Python 3.12-target, FastAPI, Uvicorn.
- SQLAlchemy 2.x ORM, PostgreSQL и Psycopg; SQLite как быстрый тестовый fallback.
- Alembic для эволюции схемы.
- Pydantic v2 / pydantic-settings для API-контрактов и конфигурации.
- Pytest для unit/service/API/integration tests.
- OpenPyXL для XLSX, ReportLab для PDF, python-multipart для импорта.
- JWT HS256 и PBKDF2-HMAC-SHA256 реализованы внутри проекта.

### Frontend

- React 19, TypeScript, Vite.
- React Router, собственный API client/auth context/i18n.
- CSS + Tailwind toolchain; UI в основном реализован собственными компонентами.
- Playwright для browser E2E и артефактов падений.

### Data/DevOps

- PostgreSQL 16, Docker, Docker Compose.
- nginx для static hosting и reverse proxy.
- GitHub Actions: SQLite backend tests, frontend typecheck/build/mock E2E, PostgreSQL migration/concurrency job и real E2E.
- Bash/PowerShell backup и restore, Makefile, env templates.
- Legacy discovery/ETL: read-only анализ InterBase/Firebird, подготовка CSV/XLSX, dry-run и reconciliation-first миграция.

### Предметные навыки

- моделирование товарного, складского, денежного и долгового учёта;
- проектирование state machines и транзакционных инвариантов;
- RBAC до уровня object/action и warehouse scope;
- конкурентный доступ, idempotency-like защита и pessimistic locking;
- обратная разработка legacy-поведения;
- контролируемая миграция данных и сверка контрольных итогов;
- тест-дизайн сквозных сценариев менеджера, кассира и логиста.

## 5. Оценка уровня разработчиков

По репозиторию подтверждается один автор, поэтому нельзя доказательно приписывать работу нескольким разработчикам. По результату профиль автора выглядит как сильный Middle Full-stack с отдельными Senior-компетенциями в backend/domain engineering.

Признаки уровня выше среднего:

- осознанный modular monolith вместо преждевременных микросервисов;
- транзакционные инварианты, `SELECT FOR UPDATE`, advisory locks и тесты конкурентной продажи;
- controlled reposting с ревизиями и аудитом;
- разделение mock и real E2E, изолированный PostgreSQL-контур;
- миграционная документация, dry-run и контрольные суммы;
- RBAC и складской data scope применены на сервере, а не только скрытием кнопок.

Что пока не даёт уверенно назвать реализацию production-grade Senior/Lead:

- собственная криптографическая/JWT-реализация вместо зрелой библиотеки и устаревший параметр PBKDF2 120k;
- дефолтный demo secret и восьмичасовой bearer token без refresh/revocation/session controls;
- нет структурированного логирования, метрик, tracing, error tracking и readiness checks;
- нет полного deployment pipeline, environment approvals, immutable image promotion и автоматического rollback;
- frontend крупный и преимущественно page-centric, без сформированного feature/domain layer и unit/component testing;
- некоторые отчётные балансы считаются динамически, что станет проблемой на большом объёме;
- legacy-правила и acceptance остаются открыты, а значит часть кода основана на временных предположениях.

Кратко: качество инженерного мышления соответствует сильному Middle+/Senior- на backend-задачах; Full-stack ширина хорошая, но production operations, security hardening и масштабирование ещё требуют опыта или участия профильных специалистов.

## 6. Что предстоит доделать

### P0 — блокирует production cutover

1. Получить безопасный read-only доступ к копии `BUY.GDB` или экспортировать из неё только справочники: товары, группы, единицы измерения, склады, партнёров и связанные классификаторы.
2. Отдельно зафиксировать cutoff и получить подписанные начальные срезы остатков/стоимости запаса, долгов и кассы. Исторические документы и платежи не переносить; это решение зафиксировать в протоколе cutover.
3. Закрыть открытые правила отмены зависимых документов, возвратов, знаков долгов, opening entries и истории кассовых отмен.
4. Провести бизнес-приёмку M01-M10 и подписать GO/NO-GO протокол.
5. Исправить текущий преобразователь прайс-листа до импорта production-данных.
6. Подготовить production identity: удалить/заблокировать demo users, сменить секреты, определить password/session policy.

### P1 — release readiness

1. Создать staging, близкий к production, и прогнать все миграции, E2E, backup/restore и reconciliation.
2. Автоматизировать сценарии M08-M10 и browser-проверки отчётов, экспорта, печати и импорта.
3. Добавить observability: JSON logs с correlation ID, метрики HTTP/DB/business failures, dashboards, alerts и централизованный error tracking.
4. Добавить readiness endpoint с DB check; оставить liveness дешёвым и независимым.
5. Провести нагрузочные тесты на согласованном объёме и concurrency profile; проверить индексы через реальные query plans.
6. Провести security review по OWASP ASVS 5.0, dependency/secret/code scanning и container scan.
7. Формализовать migration rollback: backward-compatible schema, expand/migrate/contract или обязательный restore с измеренным RTO/RPO.

### P2 — качество и развитие

1. Разбить крупные service/page modules на use cases и feature slices; выделить policy/domain helpers без HTTP/ORM-зависимостей.
2. Ввести repository/unit-of-work границы только там, где они реально облегчают тестирование; не создавать абстракции ради абстракций.
3. Добавить frontend tests: Vitest + React Testing Library для форм, permissions, formatters и error states; accessibility checks.
4. Ввести единый error contract: стабильный код, параметры, локализуемое сообщение и correlation ID.
5. Добавить pagination/filtering на сервере для растущих справочников и отчётов.
6. Версионировать API и данные экспорта формально, генерировать typed client из OpenAPI.
7. Ввести ADR, CODEOWNERS, PR template, Definition of Done и changelog/release notes.

## 7. Доработки архитектуры и кода

Рекомендуемая эволюция без переписывания:

- Сохранить modular monolith, но организовать backend по доменам (`documents`, `stock`, `payments`, `identity`) с public application services.
- Отделить команды от запросов на уровне use cases: проведение/отмена/коррекция — команды; отчёты — query services. Полный CQRS и event sourcing сейчас избыточны.
- Ввести явные state transition policies и property-based tests для финансовых/складских инвариантов.
- Для внешне повторяемых POST-запросов добавить idempotency key, особенно проведение, платеж и импорт.
- Добавить optimistic version column для пользовательского редактирования черновиков; оставить pessimistic locks для коротких критических проводок.
- Укрепить auth готовой библиотекой, Argon2id или актуальным PBKDF2-профилем, коротким access token, refresh rotation/revocation и rate limiting login.
- Перейти от вычисления тяжёлых балансов «на лету» к проверенным ledger queries, materialized views или snapshots после профилирования, сохраняя ledger source of truth.
- Сделать импорт отдельным job workflow с checksum, staging tables, preview, apply, retry и immutable import report.
- Стандартизировать события аудита: actor, action, aggregate, before/after hash, request/correlation ID, timestamp, source.
- Покрыть миграции forward/backward compatibility tests и запретить destructive migration без отдельного approval.

## 8. ТЗ на CI/CD для релиза

### Цель

Автоматически доказывать качество каждого изменения, собирать один неизменяемый комплект образов, продвигать его через staging в production и обеспечивать воспроизводимый откат без ручной пересборки.

### Ветки и управление

- Trunk-based: короткие feature branches -> PR -> protected `main`.
- PR требует минимум одного review, зелёных required checks и актуальной ветки.
- Запрет прямого push и force-push в `main`; CODEOWNERS для migrations, auth, finance и workflows.
- Conventional Commits необязательны, но release notes генерируются из PR labels.

### PR pipeline — обязательные gates

1. Checkout с pinning actions по major/SHA и минимальными permissions.
2. Python lint/format/type: Ruff и mypy/pyright; `compileall`.
3. Backend tests на PostgreSQL, а не только SQLite; coverage threshold сначала 75%, затем 85% для изменённых строк.
4. `alembic upgrade head` с чистой БД; проверка одной головы; тест миграции с предыдущего release schema.
5. Frontend `npm ci`, ESLint, TypeScript, Vitest/component tests, production build.
6. Playwright critical smoke с реальным API/PostgreSQL.
7. Dependency review, Dependabot, CodeQL/SAST, secret scan, npm/pip audit с политикой severity.
8. Docker build обоих образов, Trivy/Grype scan, проверка запуска non-root и Compose config.
9. Проверка, что не добавлены `.env`, dumps, GDB, backups, PII/financial exports или слишком большие бинарники.
10. Загрузка JUnit, coverage, Playwright traces/screenshots и SBOM независимо от успеха; чувствительные данные в артефакты не включать.

### Main/release pipeline

1. Версия: SemVer tag + commit SHA; image tags `vX.Y.Z` и `sha-...`; запрет mutable `latest` как deployment source.
2. Один раз собрать backend/frontend images, создать SBOM, подписать/аттестовать provenance и отправить в registry.
3. Автоматически развернуть эти digest в staging.
4. До приложения выполнить pre-deploy backup и dry-run/compatibility check миграций; миграции запускать отдельным one-shot job.
5. Выполнить smoke M01-M10, API contract, reconciliation fixture и synthetic transaction.
6. Production — GitHub Environment с ручным approval владельца бизнеса и DevOps, protected secrets и deployment concurrency lock.
7. Продвинуть те же image digests, выполнить migration job, rolling/recreate deployment и post-deploy smoke.
8. Автоматически прекратить rollout при failed health/smoke; приложение откатить на предыдущие digests. БД откатывать только по утверждённому runbook/restore.
9. Создать release record: SHA, image digests, migration revision, approvers, test links, backup ID и итог GO/NO-GO.

### Нефункциональные критерии приёмки

- 100% required checks green; P0/P1 defects = 0.
- Нет critical/high exploitable vulnerabilities либо есть подписанное risk acceptance со сроком.
- Обычная операция p95 <= 2 с, стандартный отчёт p95 <= 5 с на согласованном наборе данных.
- RPO и RTO согласованы; предлагаемый старт: RPO <= 24 ч, RTO <= 4 ч, затем уточнить с бизнесом.
- Restore drill проходит в отдельном окружении и завершается сверкой данных.
- 30 минут после релиза нет всплеска 5xx, ошибок транзакций, отрицательных остатков или расхождений кассы.

### Секреты и окружения

- Раздельные dev/staging/prod DB и credentials; production DB не публикуется наружу.
- Secrets только в GitHub Environments/secret manager; ротация, audit trail и least privilege.
- HTTPS на edge, secure headers/CSP, backup encryption и ограниченный доступ к логам/артефактам.
- Production конфигурация валидируется при старте: demo secret и небезопасные CORS должны приводить к fail-fast.

## 9. Роли и области ответственности на этом проекте

### Full-stack developer

Отвечает за вертикальные фичи от UI до БД: контракт API, schema migration, бизнес-правило, транзакция, React-flow, permissions, тесты и документацию. На примере «частичная оплата» — моделирует allocation, блокирует счета, исключает двойное движение кассы, реализует форму распределения и API/E2E-тесты.

Нужные навыки: Python/FastAPI, SQL/PostgreSQL, transactions/locking, React/TypeScript, REST/OpenAPI, security basics, Docker и test automation.

### QA / tester

Отвечает не только за клики, а за модель качества: risk-based test plan, контрольные числа, negative/boundary/concurrency cases, traceability M01-M10, regression, exploratory и UAT support. На примере продажи — проверяет полный/нулевой/недостаточный остаток, две строки с ошибкой во второй, повторный запрос, конфликт двух пользователей, отмену и совпадение документа/остатка/движений/долга/аудита.

Артефакты: test cases, test data, automation, defect reports P0-P3, release test report и evidence для GO/NO-GO.

### Project manager / product owner

Отвечает за границы релиза и снятие доменной неопределённости: stakeholder map, backlog, acceptance criteria, legacy decision log, migration/cutover plan, риски, зависимости, UAT и решение GO/NO-GO. На примере возврата PM не предлагает программисту угадывать: получает правило у владельца учёта, фиксирует сценарии и только затем ставит задачу.

Метрики: burn-up release scope, открытые P0/P1, доля подтверждённых legacy rules, UAT pass rate, migration reconciliation difference, lead time и change failure rate.

### DevOps / SRE

Отвечает за воспроизводимый delivery и эксплуатацию: runners, registry, environments, secrets, image provenance, deploy/migration jobs, HTTPS, DNS, DB, backups, restore drills, monitoring, alerts, capacity, incident/rollback runbooks. Не принимает бизнес-правила учёта, но гарантирует, что ровно проверенный artifact безопасно доставлен и восстановим.

Метрики: deployment frequency, lead time, change failure rate, MTTR, availability, backup success, restore duration, saturation и error budget.

### Границы совместной ответственности

- Схема/миграция: Full-stack делает; QA проверяет upgrade/data; DevOps исполняет и обеспечивает backup; PM принимает downtime/risk.
- Accounting rule: PM/владелец бизнеса утверждает; Full-stack реализует; QA доказывает сценариями; DevOps наблюдает технические симптомы.
- Релиз: DevOps оркестрирует; QA выдаёт quality sign-off; Full-stack дежурит по дефектам; PM/владелец принимает GO/NO-GO.
- Incident: DevOps стабилизирует/откатывает приложение; разработчик локализует дефект; QA воспроизводит и проверяет fix; PM управляет коммуникацией и бизнес-приоритетом.

## 10. Перспективы и актуальные рыночные фичи

Приоритет следует строить от операционной ценности, а не от модного AI.

### Следующая продуктовая волна

1. Mobile/PWA warehouse workspace и barcode/QR: приёмка, подбор, перемещение, инвентаризация, location/bin codes, offline queue. Это уже базовое ожидание WMS-класса.
2. Replenishment: min/max, reorder point, lead time, safety stock, suggested purchase orders и supplier comparison.
3. Lot/serial/expiry tracking и recall traceability — если ассортимент требует партийности.
4. Purchase orders, receiving discrepancies, return-to-supplier/customer returns и approval workflows.
5. E-invoicing/фискальные интеграции под фактическую юрисдикцию; требования нужно проверять юридически перед реализацией.
6. Notifications: low stock, overdue debt, price below margin, failed import, stalled logistics task.
7. BI dashboard: inventory turnover, aging, gross margin, dead stock, ABC/XYZ, cash forecast и collection priorities.
8. Public/integration API, webhooks и коннекторы к банку, e-commerce, бухгалтерии и BI.

### AI после накопления качественной истории

- прогноз спроса и stockout с explainability и ручным подтверждением закупки;
- предложения товара-замены при отсутствии;
- anomaly detection по цене, скидке, возврату, корректировке кассы и необычной активности;
- OCR входящих документов с обязательной human review;
- natural-language поиск по отчётам, но только поверх permission-filtered semantic layer;
- прогноз просрочки платежа и cash-flow сценарии.

AI не должен напрямую проводить финансовые/складские документы. Без очищенной истории, reconciliation и измеримой baseline-модели прогноз будет демонстрационной фичей, а не бизнес-инструментом.

## 11. Как представить проект на собеседовании

Нельзя честно утверждать неподтверждённые коммерческие факты, многолетний срок, production traffic или работу целой команды. Сильнее и безопаснее сформулировать так: «Я развиваю production-oriented модернизацию реальной legacy-системы учёта; проект дошёл до развитого MVP и подготовки cutover, а production launch зависит от миграции и бизнес-приёмки».

### Короткий pitch

«Я модернизирую legacy-приложение складского и взаиморасчётного учёта на FastAPI, PostgreSQL и React/TypeScript. Это модульный монолит с документами и проводками, складскими остатками, частичными оплатами, кассой, RBAC, аудитом и импортом данных. Самые сложные части — не CRUD, а сохранение финансовых инвариантов при проведении/перепроведении, конкурентная продажа последнего остатка и безопасный переход со старой InterBase-базы. Я построил 18 миграций, backend/API tests, Playwright real E2E на PostgreSQL и release plan с reconciliation и rollback gates».

### Лучшие технические истории по STAR

1. Конкурентная продажа: риск oversell -> row/advisory locking и атомарное проведение -> один запрос проходит, второй получает контролируемый отказ, остаток не отрицательный.
2. Коррекция проведённого документа: бизнесу нужна правка без потери истории -> revision + reversal/reapply в одной транзакции -> аудитируемое перепроведение и целостные остатки/долги.
3. Распределение платежа: partial/advance/reallocation могли задвоить кассу -> allocations отдельно от cash movement и locks -> гибкая сверка счетов без двойного движения денег.
4. Legacy migration: схема неизвестна и опасно копировать таблицы механически -> discovery, canonical templates, dry-run, control totals и exception log -> управляемый cutover вместо «импорт прошёл без ошибок».
5. Тестовая пирамида: SQLite быстро, но не проверяет PostgreSQL locking -> отдельный PostgreSQL integrity job и real browser E2E -> проверка реальных транзакционных сценариев.
6. RBAC логиста: скрытия UI недостаточно -> server-side warehouse scoping и урезанные price responses -> защита от прямого вызова API и утечки закупочной цены.

### Числа, которые можно назвать

- 49 коммитов, около 18,4 тыс. строк приложения/тестов и 3,2 тыс. строк документации.
- 18 миграций, 15 API-доменов, 197 собранных backend-тестов.
- SQLite: 193 прошли, 4 PostgreSQL-only пропущены; PostgreSQL matrix: 4 прошли.
- 5 mock E2E и 8 актуально подтверждённых real E2E-сценариев на чистом PostgreSQL.
- Импортный сценарий рассчитан на безопасную обработку прайс-листа; изученный текущий экспорт содержит 382 уникальных товара и 16 309 единиц остатка. Не выдавать план на 15 000 строк за уже измеренную production-нагрузку.

### Вопросы, к которым стоит подготовиться

- Почему modular monolith, а не microservices?
- Где проходит транзакционная граница проведения документа?
- Почему SQLite tests недостаточны для PostgreSQL concurrency?
- Как предотвратить duplicate submit и oversell?
- Как откатить релиз с необратимой миграцией?
- Как сверить legacy и новую систему до cutover?
- Как не утечь закупочной цене логисту?
- Когда динамический расчёт балансов перестанет масштабироваться?
- Чем liveness отличается от readiness?
- Какие факты доказывают production readiness, а какие пока только план?

## 12. Итоговая дорожная карта

### 0-2 недели

- стабилизировать и закоммитить/отклонить текущий WIP каталога;
- закрыть legacy decision log P0;
- обновить CI security gates и добавить frontend component tests;
- автоматизировать M08-M10;
- подготовить staging и observability minimum.

### 3-6 недель

- пробная миграция справочников и отдельных начальных срезов;
- reconciliation и исправление import pipeline;
- UAT M01-M10, performance/concurrency/security tests;
- restore drill и генеральная репетиция релиза.

### После первого стабильного релиза

- barcode/PWA warehouse flow;
- replenishment и purchasing;
- lot/serial/expiry при бизнес-необходимости;
- BI/alerts/integrations;
- только затем AI forecasting/anomaly/OCR с human-in-the-loop.

## 13. Проверка, выполненная в этом аудите

- `git` history/status и объём исходников исследованы.
- Backend: `166 passed, 2 skipped` за 42,28 с на локальной конфигурации.
- Frontend production build в этом аудите не выполнен: зависимости не установлены, команда остановилась на отсутствии `tsc`. Это не дефект исходников; результат требует `npm ci` и повторного прогона.
- Docker/PostgreSQL real E2E в этом аудите не повторялся. Использованы сохранённые в репозитории результаты предыдущих прогонов.
- Секреты, инфраструктура и legacy database не изменялись.

Актуализация 2026-10-12: Docker/PostgreSQL real E2E повторён на точных
production backend/frontend images без bind mounts. Одноразовый Compose-контур
применил Alembic head `0018`, выполнил seed/readiness и провёл все 8 сценариев
через production nginx, включая обязательную смену временного пароля логиста.
Контейнеры, сеть и tmpfs DB удалены teardown-процедурой. Первый run обновлённого
job в GitHub Actions и повтор на чистом RC SHA ещё требуются.

## 14. Внешние ориентиры

- Odoo 18 Inventory: barcode operations, product/location/package codes, mobile receipt/delivery and RFID workflows.
- Odoo 18 Replenishment: min/max reordering, manual suggestions, automatic purchase/manufacturing orders and MTO/MPS strategies.
- Microsoft Dynamics 365 Business Central: demand/stockout forecasting, item substitutes, late-payment prediction, cash-flow analysis and sales-order agents.
- OWASP ASVS 5.0: формальная основа требований и тестов web application security.
- GitHub Actions: artifact attestations/SBOM and dependency review for software supply-chain controls.
