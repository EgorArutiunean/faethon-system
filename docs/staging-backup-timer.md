# Локальные staging backups через systemd

Подготовлено 2026-10-15. Установка и первый автоматический запуск на сервере
ещё не подтверждены. Этот job создаёт только локальные копии; offsite и доставка
alerts остаются открытыми release gates.

Статическая проверка обоих units и выражения календаря прошла на systemd 257
в одноразовом Debian-контейнере. Для `Requires=docker.service` использовался
минимальный dependency fixture; реальный Docker socket не подключался. Это
подтверждает синтаксис, но не заменяет ручной запуск на целевом Ubuntu host.
Предупреждения о правах файлов на Windows bind mount устраняются установкой
service/timer с mode `0644`.

## Параметры текущего staging

- Coolify application: `Buy Modern / staging / buy-modern-staging`.
- Compose project: `l4w4kssko4ogk00sg8co480s`.
- Скрипт: `/opt/buy-modern/current/scripts/backup_postgres.sh`.
- Backup directory: `/var/backups/buy-staging`, root-only, `0700`.
- Env: `/etc/buy-modern/staging-backup.env`, root-owned, `0600`.
- Service/timer: `buy-modern-staging-backup.service` / `.timer`.
- Запуск: каждый час в `HH:05`, по timezone сервера; `Persistent=true`
  компенсирует пропущенный запуск после простоя.
- Retention: `0`, существующие копии автоматически не удаляются. Переход на
  14 дней — отдельное изменение после проверки расписания и политики хранения.

Service выполняется от существующего root: каталог и lock уже принадлежат root,
а Docker API требует привилегированного доступа. Новый пользователь с Docker
доступом не создаётся. `ProtectSystem=strict` разрешает запись только в backup
directory и metrics collector; `UMask=0077` закрывает dump/checksum.

Этот unit не запускает Restic и не требует `offsite_backup.sh` или offsite secrets.
Production unit `buy-modern-backup.service` устанавливается отдельно.

## Установка

В терминале **сервера**, от root. Используйте SHA tooling commit, предоставленный
в handoff после публикации. Все файлы загружаются из одного закреплённого commit.
Предварительно проверьте отсутствие существующего staging job:

```bash
command -v curl docker flock sha256sum systemctl systemd-analyze
systemctl list-unit-files 'buy-modern*backup*' --no-pager
docker ps --filter label=com.docker.compose.project=l4w4kssko4ogk00sg8co480s --filter label=com.docker.compose.service=postgres --format '{{.Names}} | {{.Status}}'
sha256sum /opt/buy-modern/current/scripts/backup_postgres.sh
```

Нужен ровно один healthy PostgreSQL. Ожидаемый SHA-256 уже проверенного скрипта:
`7be7ccfbb2a0200a3fb1f28ec48840eaf114016303b80df46cac56605a9791d6`.
При отличиях сначала проверить установленную версию, не перезаписывать её вслепую.

Далее скачать из выбранного commit следующие файлы во временный каталог,
проверить их SHA-256 по handoff и установить с root ownership:

| Файл в репозитории | Путь на сервере | Mode |
|---|---|---|
| `ops/systemd/buy-modern-staging-backup.service` | `/etc/systemd/system/buy-modern-staging-backup.service` | `0644` |
| `ops/systemd/buy-modern-staging-backup.timer` | `/etc/systemd/system/buy-modern-staging-backup.timer` | `0644` |
| `ops/systemd/staging-backup.env.example` | `/etc/buy-modern/staging-backup.env` | `0600` |

В env заменить только `BACKUP_COMPOSE_PROJECT=CHANGE_ME` на
`BACKUP_COMPOSE_PROJECT=l4w4kssko4ogk00sg8co480s`. Создать отсутствующие каталоги
`/etc/buy-modern` (`0755`), `/var/backups/buy-staging` (`0700`) и
`/var/lib/node_exporter/textfile_collector` (`0755`). Существующие владельцы
metrics directory и backup files не меняются.

Перед включением расписания:

```bash
systemd-analyze verify /etc/systemd/system/buy-modern-staging-backup.service /etc/systemd/system/buy-modern-staging-backup.timer
systemd-analyze calendar '*-*-* *:05:00'
systemctl daemon-reload
systemctl start buy-modern-staging-backup.service
systemctl show buy-modern-staging-backup.service -p Result -p ExecMainStatus
journalctl -u buy-modern-staging-backup.service -n 25 --no-pager
```

Ожидаются `Result=success`, `ExecMainStatus=0`, новый dump и `.sha256`,
`buy_modern_backup_last_attempt_success 1` в файле
`/var/lib/node_exporter/textfile_collector/buy_modern_staging_backup.prom`.
Проверить checksum именно нового dump. При ручном запуске `Type=oneshot`
после успеха может отображать `inactive (dead)`; результат проверяется по
`Result`/`ExecMainStatus` и созданным файлам.

Только после успешного ручного запуска включить timer:

```bash
systemctl enable --now buy-modern-staging-backup.timer
systemctl list-timers buy-modern-staging-backup.timer --all --no-pager
```

`Persistent=true` может запустить job сразу, если плановый срок уже прошёл.
Затем дождаться первого фактического автоматического запуска, проверить журнал,
новый dump/checksum и записать timestamp. Зелёный timer сам по себе не доказывает
успешный backup.

## Отключение расписания

```bash
systemctl disable --now buy-modern-staging-backup.timer
```

Команда отключает будущие запуски. Уже выполняющийся service и созданные копии
не затрагиваются.

## Ограничения

- Копия на этом VPS не защищает от потери самого VPS; нужен offsite repository
  и проверенное получение/восстановление зашифрованной копии.
- `.prom` file не подтверждает работу node_exporter, Prometheus или доставку alerts.
- Скрипт пока публикует метрики без environment/project labels. Staging и
  production нельзя одновременно публиковать одним node_exporter collector:
  разные имена `.prom` файлов не устраняют одинаковые time series. Перед таким
  размещением добавить labels и обновить alert rules либо разделить collectors.
- Сохранность пользовательских данных после Redeploy проверяется отдельным
  авторизованным smoke; readiness проверяет доступность БД и revision схемы.
