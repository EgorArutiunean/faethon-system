# Ежедневные staging backups

Политика согласована 2026-10-15: один backup в сутки, хранение 7 дней.
Дополнительная ручная копия — перед миграцией схемы или массовым импортом.
Production использует отдельный почасовой профиль.

## Статус

- [x] Первый серверный backup и изолированное восстановление проверены.
- [x] Service/timer/env установлены; ручной systemd job завершился успешно.
- [x] Daily timer и точный 7-day retention подготовлены в репозитории.
- [x] Daily/7 применено на VPS; timer включён (подтверждено оператором 15 октября).
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
| Расписание | 04:05 Europe/Chisinau ежедневно |
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
printf '%s  %s\n' 'b128aba884648c119260f4df671fca0124d4cad4362a53d5a2e8853823462422' "$STAGING_POLICY_INSTALLER" | sha256sum -c -
STAGING_TOOLING_REF="$STAGING_TOOLING_REF" sh "$STAGING_POLICY_INSTALLER"
)
~~~

Проверка календаря:

~~~bash
systemd-analyze calendar '*-*-* 04:05:00 Europe/Chisinau'
systemctl cat buy-modern-staging-backup.timer
~~~

NEXT может отображаться в UTC: 01:05 при UTC+3 и 02:05 при UTC+2.
Для подтверждения автоработы нужен новый timestamp и валидная пара dump/checksum.

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
