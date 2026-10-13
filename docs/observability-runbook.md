# Observability runbook

Актуально на 2026-10-12. В репозитории подготовлены безопасный error tracking,
Prometheus scrape/rules и Grafana dashboard. Они становятся эксплуатационно
готовыми только после подключения production Sentry DSN, Prometheus/Grafana,
node exporter, backup freshness metric и реального канала Alertmanager.

## Error tracking

Backend включает Sentry только при непустом `SENTRY_DSN`. События отправляются
с `APP_ENV`/`SENTRY_ENVIRONMENT`, `RELEASE_VERSION` и request-id. По умолчанию
PII и stack locals выключены, request body, cookies, headers, query string и
user удаляются из error events и performance transactions. Production trace sampling задаётся
`SENTRY_TRACES_SAMPLE_RATE`; стартовое значение — `0.05`.

Проверка после настройки: вызвать контролируемую тестовую ошибку только на
staging, найти событие по release/request-id и убедиться, что в нём нет токена,
пароля, cookie, query parameters и персональных данных.

## Prometheus и Grafana

- scrape config: `ops/prometheus/prometheus.yml`;
- alert rules: `ops/prometheus/alerts.yml`;
- dashboard: `ops/grafana/dashboards/buy-modern-overview.json`;
- backend metrics доступны внутри сети Compose по `backend:8000/metrics` и не
  публикуются через nginx.

Дашборд показывает request rate, 5xx ratio, p95 latency, состояние DB pool,
возраст backup и свободное место. Последние два показателя требуют node
exporter и метрики `buy_modern_backup_last_success_timestamp_seconds`.
Backup scripts публикуют last-success timestamp, last-attempt timestamp и
success flag атомарно: Linux — через `BACKUP_METRICS_FILE`, Windows — через
параметр `-MetricsFile`. Путь должен указывать в textfile collector directory
node exporter. Failed attempt сохраняет предыдущий success timestamp и меняет
`buy_modern_backup_last_attempt_success` на `0`.

## Реакция на alerts

1. `BackendDown`: проверить `/health/live`, `/health/ready`, последние JSON logs,
   состояние контейнеров и PostgreSQL. При провале после релиза — rollback.
2. `HighServerErrorRate`: найти affected route/status и request-id, сопоставить
   с Sentry release. Не перезапускать сервис до фиксации evidence.
3. `HighApiLatency`: проверить p95 по route, DB pool, slow queries, CPU/memory.
4. `DatabasePoolSaturation`: найти долгие транзакции и рост checked-out; не
   увеличивать pool вслепую без анализа PostgreSQL connections.
5. `BackupStale`/`BackupMetricMissing`: проверить job, свободное место, checksum
   и offsite replication; выполнить контролируемый backup, затем restore smoke.

## Обязательная приёмка перед production

- импортировать dashboard и зафиксировать datasource UID;
- проверить Prometheus rules утилитой `promtool check rules`;
- направить Alertmanager минимум в два канала/on-call контакта;
- отправить тестовый warning и critical alert, подтвердить доставку и recovery;
- зафиксировать владельца, escalation path и время реакции;
- подтвердить отсутствие чувствительных данных в реальном Sentry event.
