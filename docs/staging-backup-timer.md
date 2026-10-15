# Ежедневные staging backups

Политика согласована 2026-10-15: один backup в сутки, хранение 7 дней.
Дополнительная ручная копия — перед миграцией схемы или массовым импортом.
Production использует отдельный почасовой профиль.

## Статус

- [x] Первый серверный backup и изолированное восстановление проверены.
- [x] Service/timer/env установлены; ручной systemd job завершился успешно.
- [x] Daily timer и точный 7-day retention подготовлены в репозитории.
- [x] Daily/7 применено на VPS; timer включён (подтверждено оператором 15 октября).
- [x] Применён перенос с первоначальных 04:05 на согласованные 11:05 Europe/Chisinau:
  оператор подтвердил выполнение блока, проверку исходного SHA и NEXT 16 октября.
- [x] Ручной запуск service после переноса завершился успешно с retention=7.
- [x] Контрольная сумма созданного 12:51 UTC dump независимо проверена: `OK`.
- [ ] Подтверждён первый фактический автоматический запуск.
- [ ] Внешняя зашифрованная копия получена на ПК и восстановлена.

## Параметры

| Параметр | Значение |
|---|---|
| Application | Buy Modern / staging / buy-modern-staging |
| Compose project | l4w4kssko4ogk00sg8co480s |
| Service/timer | buy-modern-staging-backup.service / .timer |
| Владелец job | root |
| Скрипт | /opt/buy-modern/current/scripts/backup_postgres.sh |
| Env | /etc/buy-modern/staging-backup.env |
| Копии | /var/backups/buy-staging, root-only 0700 |
| Согласованное расписание | 11:05 Europe/Chisinau ежедневно |
| Применение на VPS | Подтверждён NEXT 2026-10-16 08:05 UTC = 11:05 Europe/Chisinau |
| Retention | 7 × 24 часа, по времени изменения файла |

Timezone указан прямо в OnCalendar. Persistent=true компенсирует пропущенный
запуск после простоя, но не гарантирует ежедневную копию при недоступности VPS.

Cleanup выполняется после создания и проверки нового backup. Удаляются только
обычные файлы верхнего уровня с точными именами buy_modern_YYYYMMDD-HHMMSS.dump
и .dump.sha256. Другие среды в этой папке не хранить. Старые подходящие копии
будут удалены после следующего успешного backup, если истёк срок хранения.
Точный cutoff на Linux использует GNU date/find; старый -mtime +N добавлял сутки.

Service выполняет только локальный backup. Restic/offsite и пароль БД ему не нужны.
ProtectSystem=strict разрешает запись только в backup directory и metrics collector.
UMask=0077 закрывает dump/checksum. Новый пользователь с Docker-доступом не создаётся.

## Подтверждённый ручной запуск

15 октября service работал в 14:21:25–14:21:26 Europe/Chisinau
(11:21:25–11:21:26 UTC в серверном журнале). Оператор подтвердил SHA-256 tooling,
создание buy_modern_20261015-112125.dump, checksum и freshness metric;
Result=success, ExecMainStatus=0. Тогда retention был 0, старые копии не удалялись.

Первоначальная установка использовала commit c0405934d583baeb749ef53941fddd6cae6de684.
Этот факт не подтверждает включение daily timer или внешнюю репликацию.

После обновления через tooling commit `87ab924f0d80a0141e44230a69b8ecf6a2ff7155`
оператор подтвердил checksum helper/script/timer, enable-ссылку в
`timers.target.wants`, `BACKUP_RETENTION_DAYS=7` и NEXT 16 октября, 01:05 UTC
(04:05 Europe/Chisinau). LAST пока отсутствует: первый автоматический job
ещё не подтверждён. Прежняя конфигурация сохранена helper в
`/tmp/buy-staging-daily.0rmuMq`; это временный rollback-каталог, не резервная копия БД.

Позже 15 октября пользователь перенёс согласованное время на 11:05. Исходный
timer обновлён; оператор выполнил блок смены часа с успешной проверкой исходного
SHA. Полный вывод после перезапуска: NEXT `2026-10-16 08:05:00 UTC`, то есть
11:05 Europe/Chisinau; LAST `2026-10-15 12:06:24 UTC`. Журнал сервиса на момент
проверки содержит только ручной backup в 11:21 UTC с retention=0, новых записей
после отметки LAST нет. LAST не подтверждает успешный backup job. Первый
автоматический backup тогда ещё не был проверен.
Исторический NEXT выше относится к первоначальным 04:05.

Позже оператор вручную запустил service в 12:51:33–12:51:34 UTC. Журнал
подтверждает `buy_modern_20261015-125133.dump`, соответствующий `.sha256`,
freshness metric, `Retention applied: 7 days` и успешное завершение сервиса.
Скрипт до публикации dump выполняет `pg_restore --list`. После сервиса оператор
выполнил `sha256sum -c buy_modern_20261015-125133.dump.sha256` из backup-каталога:
`buy_modern_20261015-125133.dump: OK`. Восстановление именно этой пары ещё не
проведено; более ранний dump уже проверяли изолированным restore drill.
Ручной запуск не закрывает проверку первого автоматического backup 16 октября.

## Обновление установленного staging до daily/7

На VPS от root сначала задать STAGING_TOOLING_REF полным SHA из handoff.
Все файлы скачиваются из одного pinned commit. Команды проверяют project,
backup directory, SHA-256 и сохраняют предыдущую конфигурацию во временную папку.

Helper `scripts/configure_staging_backups.sh` принимает только согласованный
Compose project, проверяет текущую версию backup script и скачанные файлы перед
заменой, затем включает daily timer. Автоматическая очистка старых подходящих
копий начнётся при следующем успешном backup с retention=7.

~~~bash
(
set -eu
: "${STAGING_TOOLING_REF:?Укажите полный SHA tooling commit из handoff}"
STAGING_POLICY_INSTALLER="$(mktemp /tmp/buy-staging-policy.XXXXXX)"
curl --fail --show-error --silent --location "https://raw.githubusercontent.com/EgorArutiunean/faethon-system/$STAGING_TOOLING_REF/scripts/configure_staging_backups.sh" --output "$STAGING_POLICY_INSTALLER"
printf '%s  %s\n' 'e4cdbded993e23678eb54f572ca93de55f0899de811f4b776b8777300fc7f009' "$STAGING_POLICY_INSTALLER" | sha256sum -c -
STAGING_TOOLING_REF="$STAGING_TOOLING_REF" sh "$STAGING_POLICY_INSTALLER"
)
~~~

Проверка календаря:

~~~bash
systemd-analyze calendar '*-*-* 11:05:00 Europe/Chisinau'
systemctl cat buy-modern-staging-backup.timer
~~~

NEXT может отображаться в UTC: 08:05 при UTC+3 и 09:05 при UTC+2.
Для подтверждения автоработы нужен новый timestamp и валидная пара dump/checksum.

Если daily/7 уже установлен, для смены только времени с 04:05 на 11:05
достаточно следующего блока. Он требует точного SHA ранее установленного
timer, сохраняет его в отдельный временный файл и меняет только час.
Приложение, БД, backup script и retention не затрагиваются; новый timer
совпадает с исходником репозитория. При другом содержимом timer блок
остановится до изменений: сначала нужно проверить фактическую конфигурацию.

~~~bash
(
set -eu
STAGING_TIMER=/etc/systemd/system/buy-modern-staging-backup.timer
test -f "$STAGING_TIMER" && test ! -L "$STAGING_TIMER"
printf '%s  %s\n' 'ec70a3a93a48b0a9e3979e51ff5d72db458f8d02f9684537fff601154b671587' "$STAGING_TIMER" | sha256sum -c -
STAGING_TIMER_BEFORE="$(mktemp /tmp/buy-staging-timer-before.XXXXXX)"
cp -p "$STAGING_TIMER" "$STAGING_TIMER_BEFORE"
sed -i 's/04:05:00/11:05:00/' "$STAGING_TIMER"
systemctl daemon-reload
systemctl restart buy-modern-staging-backup.timer
systemctl list-timers buy-modern-staging-backup.timer --all --no-pager
printf 'Previous timer saved in: %s\n' "$STAGING_TIMER_BEFORE"
)
~~~

~~~bash
systemctl show buy-modern-staging-backup.service -p Result -p ExecMainStatus
journalctl -u buy-modern-staging-backup.service -n 20 --no-pager
~~~

Type=oneshot после успеха может быть inactive (dead); проверять success/0 и файлы.
Checksum нового dump проверяется из /var/backups/buy-staging.

## Отключение расписания

~~~bash
systemctl disable --now buy-modern-staging-backup.timer
~~~

Уже выполняющийся job и созданные копии эта команда не затрагивает.

## Мониторинг и внешняя копия

- Для daily staging нужен stale-порог 26 часов, учитывающий DST. Существующие
  75-minute alerts относятся к почасовому production; их не подключать к daily
  staging без изменения порога. Мониторинг пока не введён в эксплуатацию.
- Метрики без environment/project labels нельзя одновременно публиковать для
  staging и production одним node_exporter collector: имена .prom не разделяют серии.
- Создание .prom не подтверждает scrape или доставку alerts.
- Пользователь выбрал C:\Users\Egor\Projects\BuyModern-backups.
  Папка создана, но внешняя копия ещё не получена: non-interactive SSH-вход с ПК
  не прошёл; отдельный ключ подготовлен и ожидает ограниченной авторизации на VPS.
  [Следующие шаги для ПК](pc-backup.md).
- Выключенный ПК не получает обновления; локальный daily job VPS работает независимо.
