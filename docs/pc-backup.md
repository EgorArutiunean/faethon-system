# Внешняя staging-копия на Windows ПК

Пользователь выбрал папку «Проекты». Проверен существующий путь
`C:\Users\Egor\Projects`; создан отдельный каталог
`C:\Users\Egor\Projects\BuyModern-backups`. Другие проекты не изменялись.

## Фактический статус на 2026-10-15

- [x] Путь выбран и папка создана.
- [x] Доступны Windows OpenSSH client и PowerShell 7.
- [x] Выполнен read-only SSH preflight с BatchMode и StrictHostKeyChecking.
- [x] Выбранная папка закрыта ACL для текущего Windows-пользователя и SYSTEM.
- [x] Создан отдельный Ed25519 ключ в `access/staging_readonly_ed25519`.
- [x] Установлен portable Restic 0.19.1 в `tools/restic-0.19.1/restic.exe`.
- [x] Подготовлены ограниченный серверный exporter и Windows pull-клиент.
- [ ] ПК авторизован на сервере для чтения backup directory.
- [ ] Подготовлен локальный зашифрованный repository и recovery password.
- [ ] Пройден ручной цикл скачать → проверить SHA-256 → зашифровать → восстановить.
- [ ] Настроено повторение при включённом ПК и обработка пропущенных запусков.

Preflight `ssh root@78.46.186.197 true` вернул
`Permission denied (publickey,password)`. Host key checking не отключалось,
пароли и приватные ключи не запрашивались. Это отказ автоматического входа
с существующими настройками; интерактивный пароль сервера не проверялся.
Системный PATH не менялся: используется отдельный portable Restic в backup folder.
Фактические дампы в новую папку пока не загружались.

Официальный release — [Restic v0.19.1](https://github.com/restic/restic/releases/tag/v0.19.1).
Проверены GitHub asset digests и запись в `SHA256SUMS`:

- Windows AMD64 zip: `da948ad707ed690426473aaba2046cd61f8f90f6f0e7dab6be0d5796531de67d`.
- SHA256SUMS manifest: `fb520966ee01d2a3d4219c66762c66efa56300833b6f639f36082b7462f91cb8`.

На VPS передаётся только public key. Private key остаётся в закрытой папке ПК;
он предназначен для forced-command `list/get`, а не произвольных root-команд.

## Реализация и ограничения доступа

`scripts/export_staging_backup.sh` — forced command для отдельного ключа:
принимает только `list` или `get BASENAME`. Каталог фиксирован в исходнике:
`/var/backups/buy-staging`. Перед выдачей проверяется завершённая пара
dump/checksum; путь из checksum не исполняется. Shell-команды, SCP/SFTP,
произвольные пути, symlinks, partial/пустые/повреждённые копии не выдаются.
Сервис не получает Docker socket и не изменяет БД или её резервные копии.

`scripts/authorize_pc_backup.sh` запускается оператором от root один раз.
Он скачивает exporter из полного pinned commit и проверяет SHA-256, сохраняет
прежний `authorized_keys` в root-only rollback-каталоге и добавляет ровно один
ключ с `restrict,command="/bin/sh .../export_staging_backup.sh"`. Другие ключи
сохраняются, дубли того же ключа с другими опциями отклоняются. `sshd_config`
не меняется, перезапуск SSH не требуется. Ключ всё ещё относится к root:
ограничение обеспечивается OpenSSH forced command и проверенным exporter,
а не отдельным непривилегированным Linux-пользователем.

Для установки оператор получает полный SHA commit и SHA-256 helper. На VPS
задаются `PC_BACKUP_TOOLING_REF` и `PC_BACKUP_PUBLIC_KEY` (содержимое файла
`access/staging_readonly_ed25519.pub`, не private key), после чего выполняется:

~~~bash
(
set -eu
: "${PC_BACKUP_TOOLING_REF:?Укажите полный tooling commit SHA из handoff}"
: "${PC_BACKUP_PUBLIC_KEY:?Укажите отдельный публичный ключ ПК}"
PC_BACKUP_INSTALLER="$(mktemp /tmp/buy-pc-key.XXXXXX)"
curl --fail --show-error --silent --location "https://raw.githubusercontent.com/EgorArutiunean/faethon-system/$PC_BACKUP_TOOLING_REF/scripts/authorize_pc_backup.sh" --output "$PC_BACKUP_INSTALLER"
printf '%s  %s\n' 'cf7c65e815b4065911bd387d9c975ff7d65a9801ab34a7624c1bde25eb4a72b1' "$PC_BACKUP_INSTALLER" | sha256sum -c -
PC_BACKUP_TOOLING_REF="$PC_BACKUP_TOOLING_REF" PC_BACKUP_PUBLIC_KEY="$PC_BACKUP_PUBLIC_KEY" sh "$PC_BACKUP_INSTALLER"
)
~~~

`scripts/pull_staging_backup.ps1` требует Windows/PowerShell 7. ПК инициирует
исходящее SSH-соединение: входящие Windows-порты и пароль PostgreSQL не нужны.
Проверка host key обязательна; автоматическое доверие неизвестному ключу
не включается. Client использует отдельную identity, не читает пользовательский
SSH config и не разрешает forwarding или интерактивный пароль.

Дампы передаются как бинарные байты через pipe, не через текстовый PowerShell
redirect. Имена и размеры проверяются; SHA-256 сверяется до шифрования.
Локальный Restic repository — `BuyModern-backups/repository`. Скачиваются все
доступные ещё не сохранённые пары, а не только последняя. Snapshot tags содержат
источник и basename. Удаления на сервере не зеркалируются на ПК; `forget/prune`
клиент не вызывает.

Plaintext существует только в собственном GUID-каталоге `.incoming` с закрытым
ACL, затем удаляется, включая обычные ошибки. Удаление файлов не равно
криптографическому стиранию SSD; внезапное выключение может оставить временные
файлы. Для защиты диска ПК дополнительно подходит полнодисковое шифрование.
Пересекающиеся запуски блокируются; reparse points/junctions отклоняются.

## Подключение и первый ручной цикл

1. Настроить отдельный ключ для чтения staging backups. Не выдавать unattended
   backup-задаче возможность выполнять произвольные root-команды; ограничить
   доступ каталогом `/var/backups/buy-staging` и чтением завершённых копий.
   Для серверной части потребуется действие оператора в Coolify terminal.
2. До первого encrypted pull проверить `list` с отдельной identity, а также
   отказ команды `true`. Не отключать host key checking; если ключ VPS неизвестен
   или изменился, сверить fingerprint с доверенным терминалом оператора.
3. Для хранения использовать Restic с переносимым recovery password. Пароль
   не короче 16 символов вводится локально и повторно подтверждается;
   независимая копия ключа хранится отдельно в password manager/recovery storage.
   DPAPI-only шифрование нельзя считать переносимым recovery после переустановки ПК.
4. Первый запуск из локальной PowerShell 7 (не в терминале VPS):

~~~powershell
& 'C:\Users\Egor\Buy\buy-modern\scripts\pull_staging_backup.ps1' `
  -SshTarget 'root@78.46.186.197' `
  -IdentityFile 'C:\Users\Egor\Projects\BuyModern-backups\access\staging_readonly_ed25519' `
  -ResticExe 'C:\Users\Egor\Projects\BuyModern-backups\tools\restic-0.19.1\restic.exe' `
  -InitializeRepository -VerifyRoundTrip
~~~

Пароль вводится в скрытом локальном prompt, не в командной строке и не в чате.
Сохранить независимую recovery-копию до ввода. Для существующего repository
`-InitializeRepository` убрать: скрипт не перезаписывает существующий каталог,
даже если предыдущая инициализация была прервана. `-VerifyRoundTrip` расшифровывает
dump обратно во временный файл и сверяет SHA-256, включая уже сохранённые
снимки, которые ещё доступны на сервере. Повторная проверка не создаёт дубль.
Это проверка транспортировки и шифрования, а не восстановления PostgreSQL.

5. После encrypted pull отдельно восстановить расшифрованный dump в изолированный
   PostgreSQL без сети и общего staging volume; сверить schema revision, counts
   и контрольные суммы. Ранее выполненный серверный restore drill не доказывает
   восстановимость ещё не полученной копии на ПК.
6. Только после ручного полного цикла настроить Windows Task Scheduler:
   ежедневная попытка при доступном ПК и catch-up после входа/пропущенного запуска.
   Серверные удаления не зеркалировать автоматически на ПК.

## Проверки реализации

На синтетических данных, без чтения рабочих dump/private key:

- Linux exporter: 48 тестов пройдены; Ruff lint/format и shell syntax — PASS.
- Helper авторизации проверен в одноразовом Linux-контейнере: сохранение старого
  ключа без завершающего LF, точное ограничение нового, повторный запуск,
  отказы при дубликатах/некорректных ключах/неизвестном exporter.
- Полный последовательный Windows-прогон: `20 tests ... OK`, 95.9 секунды;
  включает настоящий Restic 0.19.1 encryption/decryption round trip, повторную
  проверку существующего снимка и retry после повреждённого round-trip.
- Два ранних полных прогона упирались в 60-second timeout первого синтетического
  случая. Целевые повторы (4–9 секунд) и финальный полный прогон прошли; причину
  задержки не установили, timeout не увеличивали. Повторение на Windows CI
  остаётся независимой проверкой, а не предполагаемым успехом.
- Совместная Linux-регрессия exporter + backup scripts: `81 passed`.
  Добавлен Windows CI job `pc-backup-client` с проверенным pinned Restic;
  удалённый CI ещё не подтверждён. Actionlint — PASS.

Эти проверки не означают, что реальные staging-данные уже скопированы на ПК.

## Границы надёжности

VPS независимо создаёт ежедневный backup и хранит 7 дней. Выключенный ПК не
получает новые копии: возраст внешней копии равен времени после последней успешной
синхронизации. Если ПК отсутствует дольше server retention, часть истории не
попадёт на него. Для staging это согласованный практический вариант; production
требует отдельно согласованного постоянно доступного offsite-хранилища.

Бинарные dumps, repository, SSH private key и recovery password не коммитить
в Git. Исходный `BUY.GDB` сохранять отдельной неизменяемой копией.
