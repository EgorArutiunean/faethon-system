# Backup/restore safety — локальная проверка 2026-10-15

## Граница работ

Только локальный код, тесты и одноразовые контейнеры Docker Desktop. Сервер,
Coolify, рабочие БД и business logic не изменялись. Изменения ещё не установлены
на staging; проверка синтетических данных не является production restore drill.

## Что исправлено

- Restore: удалены неявная production-цель и `--clean`; обязательны project,
  expected database, confirmation `project/database` и корректный SHA-256 sidecar.
- До записи проверяются единственный контейнер, точное имя и пустота БД.
- `--single-transaction --exit-on-error --no-owner --no-acl` обеспечивает rollback
  незавершённого restore; пользовательские роли/ACL настраиваются отдельно.
- PowerShell 7 передаёт бинарный dump потоком в Docker без `cmd.exe` interpolation.
- Backup: lock на каталог и отказ от перезаписи существующего timestamp;
  точный шаблон retention и закрытые Linux permissions dump/checksum.
- Offsite: проверяется именно отправляемый dump, а не имя из checksum sidecar.
- Метрики доступны отдельному node_exporter; backup-файлы остаются закрытыми.
- systemd template: `/bin/sh` вместо запуска файла с Git mode `100644`,
  отдельный writable cache Restic и optional mount ключа для local-only режима.
- `.gitattributes` закрепляет LF для shell-скриптов на Windows.

## Проверки

- `backend/tests/test_backup_scripts.py`: **27 passed** на Linux в локальном
  контейнере без сети. Включены corrupted/missing checksum, неверная/неоднозначная
  цель, непустая БД, restore error, lock, timestamp collision, retention=0,
  посторонние файлы, permissions и перенос CRLF checksum из Windows в Linux.
  Docker/Restic в unit-тестах заменены заглушками.
- `scripts/smoke_backup_restore.py`: **PASS**, реальный PostgreSQL 16 по digest
  `sha256:71e27bf60b70bded003791b5573f8b808365613f341df20ffcf0c1ed7bc13ddf`.
  Два новых контейнера, `network=none`, без host ports, PGDATA в tmpfs.
- Реальный custom dump создан Windows backup-скриптом. Оба restore-скрипта
  (PowerShell 7 и POSIX через Git Bash) восстановили 3 синтетические строки,
  сумму `136.29` и UTF-8 наименование. Повторный restore отказал, данные сохранились.
- Специальный archive с отсутствующей dependency `needed_function()` вызвал
  ошибку после начала restore; обе реализации откатили созданные таблицы.
- Финальный повтор runtime smoke занял **40.9 s**; это время теста, не RTO проекта.
- Временные контейнеры/PGDATA удалены, отсутствие ресурсов с тестовым label
  проверено. Рабочие базы не использовались даже как источник backup.
- Ruff lint/format, shell syntax, PowerShell parse и actionlint: **PASS**.
- Полная локальная backend-регрессия: **234 passed, 4 skipped** за 67.02 s.
  Четыре PostgreSQL-only теста пропущены в SQLite-прогоне; синтетический restore
  проверен отдельно, это не замена PostgreSQL business/concurrency suite.
  Осталось одно предупреждение стороннего testclient об устаревающем httpx API.

## Что это НЕ подтверждает

- SHA-256 не удостоверяет доверенность SQL внутри dump.
- Реальные backup, offsite encryption/restore, retention, расписание и доставка
  alert/recovery на сервере не проверялись; S3/Restic credentials не запрашивались.
- systemd runtime не проверен на Windows; template требует server acceptance.
- Новый Linux CI job `backup-restore` и весь push-CI успешно прошли на commit
  [`048327f`](https://github.com/EgorArutiunean/faethon-system/commit/048327f7bea61088cf1255d9034719eeac8567d2):
  [CI #19](https://github.com/EgorArutiunean/faethon-system/actions/runs/38720082325).
- Не проверялись application login/dashboard на этих синтетических БД, UAT,
  реальные RPO/RTO и фактические image digest'ы Coolify.

Следующий серверный шаг: подтвердить точный проект и images, установить проверенные
скрипты, получить реальный backup и восстановить его в отдельный контур.
Offsite destination и alert channel по-прежнему выбирает владелец проекта.
