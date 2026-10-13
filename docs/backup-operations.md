# Backup operations runbook

Актуально на 2026-10-13. Цель расписания — локальный validated backup каждый
час, retention 14 дней, клиентски зашифрованная Restic-копия вне production-host
и Prometheus-сигнал после каждого локального/offsite шага.

## Что подготовлено

- `scripts/backup_postgres.sh` и `.ps1`: atomic custom dump, `pg_restore --list`,
  SHA-256, scoped retention и success/failure metrics;
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

1. Создать пользователя `buy-modern`, каталоги `/var/backups/buy-modern`,
   `/var/lib/node_exporter/textfile_collector`, `/etc/buy-modern`; выдать только
   необходимые owner/group permissions. Добавление в group `docker` фактически
   даёт root-equivalent доступ и требует отдельного одобрения DevOps.
2. Разместить checkout/release tooling в `/opt/buy-modern/current` и проверить,
   что путь не изменяется между deploy.
3. Установить Restic из доверенного package repository и закрепить допустимую
   версию средствами host configuration management.
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
