# Backup operations runbook

Актуально на 2026-10-15. Цель production-расписания — локальный validated backup каждый
час, retention 14 дней, клиентски зашифрованная Restic-копия вне production-host
и Prometheus-сигнал после каждого локального/offsite шага.

Для текущего staging пользователь согласовал другой профиль: ежедневно в 11:05
Europe/Chisinau, хранение 7 дней и внешняя зашифрованная копия на ПК. Подготовка
и фактическая установка отслеживаются в [staging runbook](staging-backup-timer.md).
Production timer и его 75-minute alerts этой настройкой не изменяются.

## Что подготовлено

- `scripts/backup_postgres.sh` и `.ps1`: atomic custom dump, `pg_restore --list`,
  SHA-256, scoped retention, блокировка параллельного запуска, запрет перезаписи
  существующего timestamp и success/failure metrics;
- `scripts/restore_postgres.sh` и `.ps1`: явный project/database, обязательный
  checksum, только пустая БД, единая транзакция с остановкой при первой ошибке;
- `scripts/smoke_backup_restore.py`: синтетическая репетиция на двух новых
  контейнерах без сети/host ports, с временным PGDATA и cleanup по owner label;
- `ops/systemd/buy-modern-backup.service`: hardened one-shot job;
- `ops/systemd/buy-modern-backup.timer`: каждый час в `HH:05`;
- `ops/systemd/backup.env.example`: production paths и Compose project;
- `scripts/offsite_backup.sh`: повторная проверка SHA-256 и отправка пары
  dump/checksum в существующий Restic repository с client-side encryption;
- `ops/prometheus/alerts.yml`: отдельные failed/stale/missing alerts для
  локального и offsite backup.

Backup job находит единственный running PostgreSQL container по Docker Compose
labels `project + service=postgres`. Поэтому scheduler не читает временный CD
env-файл и не получает пароль БД. Доступ к Docker socket всё равно является
привилегированным и должен принадлежать только dedicated deployment user.

## Установка на Linux host

Для текущего Coolify staging с уже созданным root-only backup directory
используйте [отдельную инструкцию и units](staging-backup-timer.md). Следующие
шаги описывают целевую production-установку с offsite и отдельным пользователем.

1. Создать пользователя `buy-modern`, каталоги `/var/backups/buy-modern`,
   `/var/lib/node_exporter/textfile_collector`, `/etc/buy-modern`; выдать только
   необходимые owner/group permissions. Добавление в group `docker` фактически
   даёт root-equivalent доступ и требует отдельного одобрения DevOps.
   Backup directory: owner `buy-modern`, mode `0700`. Textfile collector:
   owner с правом записи backup job, mode `0755`; node_exporter должен иметь
   право прохода через родительские каталоги. `.prom` содержит только числа и
   публикуется с mode `0644`; dump/checksum на Linux — с mode `0600`.
2. Разместить checkout/release tooling в `/opt/buy-modern/current` и проверить,
   что путь не изменяется между deploy.
3. Установить Restic из доверенного package repository и закрепить допустимую
   версию средствами host configuration management. Проверить наличие `flock`
   (util-linux). Windows backup использует file lock; restore требует PowerShell 7+.
4. Создать отдельный bucket/repository вне production account/host, включить
   provider-side versioning/object lock и lifecycle policy. Выдать credentials
   только на этот repository, без прав к production DB и compute.
5. Создать криптографически случайный Restic password в
   `/etc/buy-modern/restic-password`, owner `buy-modern`, mode `0600`. Хранить
   вторую копию ключа в утверждённом
   secrets manager; потеря ключа означает потерю backup.
6. Скопировать `ops/systemd/backup.env.example` в
   `/etc/buy-modern/backup.env`, права `0600`, owner `root`.
7. Однократно инициализировать repository: `restic init`. Скрипт намеренно не
   создаёт repository автоматически, чтобы ошибка URL не породила ложный backup.
8. Установить `.service` и `.timer` в `/etc/systemd/system`, затем выполнить
   `systemctl daemon-reload` и ручной `systemctl start buy-modern-backup.service`.
   Unit запускает оба скрипта через `/bin/sh` (Git executable bit не требуется).
   `CacheDirectory=buy-modern-restic` создаёт закрытый writable Restic cache
   `/var/cache/buy-modern-restic`, не зависящий от home при `ProtectHome=true`.
   При `OFFSITE_BACKUP_ENABLED=false` отсутствие файла Restic password не мешает
   запуску локального backup; при `true` скрипт обязан проверить наличие/права ключа.
9. Проверить dump, checksum, `restic snapshots --latest 1`, журнал сервиса и
   оба `.prom` файла в textfile collector. В логах не должно быть credentials.
10. Включить `systemctl enable --now buy-modern-backup.timer`; проверить
   `systemctl list-timers buy-modern-backup.timer`.
11. На staging выполнить отдельные failed-job drills для локального backup и
   offsite repository, подтвердить доставку alert/recovery.

## Retention safety

`BACKUP_RETENTION_DAYS=14` удаляет только файлы верхнего уровня, точно
соответствующие `buy_modern_YYYYMMDD-HHMMSS.dump` и `.dump.sha256`. Значение `0`
отключает удаление. Скрипты запрещают использовать filesystem root как backup
directory. Retention выполняется только после успешного validated backup.
Файл `.backup.lock` не удалять во время работающего backup: блокировка относится
к открытому файлу. После завершения/падения процесса lock освобождается ядром.
Один backup directory должен принадлежать одному источнику БД.

Новая Linux-реализация использует точный UTC cutoff в секундах (GNU date/find),
как и PowerShell elapsed-time cutoff, вместо округления `-mtime +N`. Поэтому
retention=7 означает 7×24 часа; очистка происходит при следующем успешном job.

## Безопасное восстановление (изменение интерфейса 2026-10-15)

У restore больше нет defaults `.env.production`/`docker-compose.prod.yml` и нет
режима `--clean`. Старые вызовы с `ComposeFile`/`EnvFile` нужно заменить.
Создайте отдельный PostgreSQL container/volume с уникальным Compose project,
service label `postgres` и пустой БД в `POSTGRES_DB`. Не подключайте к нему
приложение до окончания проверки. Скрипт сам контейнер/базу не создаёт.

Пример для уже созданного **изолированного** проекта `buy-restore-drill` и БД
`buy_restore` (имена нужно сверить с реальной тестовой целью):

```bash
RESTORE_COMPOSE_PROJECT=buy-restore-drill \
RESTORE_EXPECTED_DATABASE=buy_restore \
RESTORE_CONFIRM=buy-restore-drill/buy_restore \
sh scripts/restore_postgres.sh /secure/backups/buy_modern_YYYYMMDD-HHMMSS.dump
```

```powershell
pwsh -NoProfile -File scripts/restore_postgres.ps1 `
  -BackupFile 'C:\secure\backups\buy_modern_YYYYMMDD-HHMMSS.dump' `
  -ComposeProject buy-restore-drill -ExpectedDatabase buy_restore `
  -ConfirmRestore buy-restore-drill/buy_restore
```

Рядом обязателен `.dump.sha256`: одна строка `lowercase_sha256  basename.dump`
(два пробела). Проверяется сам переданный dump, независимо от текущей директории.
Выбор контейнера должен дать ровно один результат; имя БД сверяется до записи.
При существующих пользовательских таблицах/функциях/типах/схемах restore откажет.
Ошибка `pg_restore` откатывает транзакцию, а не оставляет частичный результат.
Владельцы/ACL из dump не импортируются; доступ настраивается отдельно.

SHA-256 подтверждает целостность, но не доверенность: dump содержит исполняемый
SQL. Использовать только backup из доверенного источника. Пустая БД и explicit
confirmation не заменяют изоляцию и проверку project label оператором.
Для production recovery сначала восстановить отдельную БД и сверить данные;
переключение приложения — отдельная согласованная операция, не часть скрипта.

## Репетиция без доступа к серверу

На Linux с Docker/Python 3 и уже загруженным закреплённым PG16 image:

```bash
python scripts/smoke_backup_restore.py
```

На Windows нужны Python 3 и PowerShell 7 в PATH; для дополнительной проверки
POSIX restore:

```powershell
python scripts/smoke_backup_restore.py --shell 'C:/Program Files/Git/bin/bash.exe'
```

Скрипт не скачивает image автоматически, не использует существующие БД и
создаёт только синтетические данные. При обычном успехе/ошибке удаляет только
свои контейнеры по сохранённым ID с проверкой уникального owner label. При
принудительном завершении процесса проверить оставшиеся ресурсы с label
`buy-modern.restore-drill`; не применять глобальный Docker prune.
В CI добавлен отдельный job `backup-restore`. Локальное evidence:
[backup-safety-2026-10-15.md](backup-safety-2026-10-15.md).

## Проверки и реакция

- `buy_modern_backup_last_attempt_success = 0`: немедленно проверить job/logs,
  Docker/PostgreSQL, filesystem capacity и permissions;
- last success старше 75 минут: считать целевой RPO нарушенным или близким к
  нарушению, выполнить backup и проверить offsite replication;
- metric missing: проверить node exporter textfile collector и timer;
- `buy_modern_offsite_backup_last_attempt_success = 0`: локальный dump может
  оставаться валидным, но проверить repository URL, credentials, quota и сеть;
- offsite last success старше 75 минут либо metric missing: production release
  блокируется до восстановления репликации;
- после исправления обязательно проверить `pg_restore --list`, checksum и
  выполнить restore drill по `docs/restore-drill-2026-10-12.md`.

## Offsite restore drill

1. На изолированном staging-host получить список через `restic snapshots`.
2. Восстановить выбранный snapshot в новый пустой временный каталог, не поверх
   production backup directory.
3. Проверить `.sha256`, затем `pg_restore --list`.
4. Восстановить dump в отдельную PostgreSQL database и выполнить reconciliation,
   readiness/login/dashboard smoke.
5. Зафиксировать snapshot ID, фактические RPO/RTO и удалить временные данные по
   утверждённой процедуре. Никогда не публиковать Restic password в CI artifacts.

## Открытые production gates

- установить/включить timer на реальном host;
- создать реальный offsite repository, credentials/object lock и пройти restore;
- проверить Alertmanager delivery/recovery channel;
- измерить фактические RPO/RTO на staging и получить business approval.
