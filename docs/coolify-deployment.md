# Buy Modern: деплой через Coolify

Актуально на 2026-10-15. Цель первого запуска — staging/UAT. Production GO
требует бизнес-приёмки, решения по начальным данным и проверенного восстановления.
Инструкция подходит для существующего Coolify и подключённого Linux-сервера
Hetzner/Contabo. Устанавливать ещё один Coolify на deployment-сервер не требуется.

## 1. Что подготовлено в репозитории

- `docker-compose.coolify.yml`: PostgreSQL → миграция → backend → frontend.
- `.env.coolify.example`: имена переменных и опубликованная пара образов RC2.
- `scripts/check_coolify_compose.py`: проверка конфигурации в CI.
- `scripts/smoke_coolify_compose.py`: изолированная проверка запуска и отказа
  миграции с временной БД; не заменяет проверку на реальном Coolify.
- `release.yml`: значение `delivery=coolify-manual` публикует GHCR-образы и
  manifest, не запускает старые jobs для self-hosted runners.
- `docker-compose.release.yml` и `rollback.yml` остаются для прежней схемы.
  Workflow с названием `Legacy self-hosted production rollback (not Coolify)`
  не предназначен для серверов, управляемых Coolify.

Начальный способ доставки — **ручной Deploy в Coolify по manifest**. Автоматическое
обновление переменных через Coolify API/webhook в этой версии не реализовано.
Обычный webhook сам по себе не меняет digest: он повторно запускает сохранённую
конфигурацию. Для будущей автоматизации понадобятся обновление пары digest'ов,
ожидание результата deployment, внешние smoke-проверки и approval production.

## 2. Сервер и доступ

На нужном deployment-сервере проверьте через SSH:

```bash
uname -m
free -h
df -h
docker system df
docker stats --no-stream
```

RC2 собран для Linux AMD64: ожидается `x86_64`. Для ARM потребуется новая
сборка образов. Практический начальный резерв для одного staging: около 4 GB
доступной RAM и 30 GB диска; это запас для тестового запуска, а не измеренное
потребление или гарантия производительности. Учитывайте другие проекты и пики.

Если сервер ещё не подключён: Coolify → Servers → Add Server → IP/SSH user/key
→ Validate connection. Проверяйте именно выбранный сервер назначения.
Проверка может устанавливать Docker: на уже занятом сервере сначала согласуйте
окно обслуживания. На существующем рабочем сервере переустановка не нужна.

Firewall: HTTP/HTTPS `80/443` для proxy; SSH `22` от сервера Coolify и вашего
административного IP. PostgreSQL `5432` и backend `8000` публично не открывать.
Если Coolify установлен на этом же сервере, сохраняйте работающий доступ к панели;
его сетевые настройки не следует заменять правилами для удалённого worker-сервера.

## 3. Создайте приложение в Coolify

1. Опубликуйте изменения конфигурации из этого репозитория в GitHub. Coolify
   должен видеть commit с `docker-compose.coolify.yml`; в старом теге RC1 этого
   файла нет. Commit конфигурации и SHA образов — разные поля release record.
2. Создайте Project `Buy Modern`, Environment `staging`.
3. Добавьте **Application из Git repository**, например Public Repository
   для `https://github.com/EgorArutiunean/faethon-system`, либо через GitHub App.
4. Выберите deployment-сервер и Docker Compose build pack.
5. Branch: `main`. Base Directory: `/`. Compose Location:
   `/docker-compose.coolify.yml`. В этом GitHub-репозитории файлы находятся в
   корне; локальное имя папки `buy-modern` в Base Directory добавлять не нужно.
6. Загрузите Compose (Load/Reload Compose File; название зависит от версии).
7. Используйте обычный управляемый режим Compose, **Raw mode выключен**.
8. Выключите автоматический деплой на push и preview deployments. Первый
   rollout и последующие обновления выполняются после проверки release manifest.
9. Оставьте Connect to predefined/shared network выключенным: PostgreSQL,
   backend и nginx общаются внутри сети этого ресурса по именам сервисов.

Не создавайте отдельную БД через кнопку Add Database: эта конфигурация уже
содержит PostgreSQL. Для staging и production нужны разные Coolify Applications,
разные volumes и секреты. Общий сервер возможен для тестов, но не изолирует
окружения от отказа диска/хоста или нехватки ресурсов.

## 4. Доступ к опубликованным образам

GitHub repository и GHCR packages имеют отдельную видимость. Если packages
приватные, настройте Docker registry login **на deployment-сервере от того SSH
пользователя, которого использует Coolify**. Токен GitHub должен иметь доступ
к этим packages и `read:packages` (при наличии SSO — соответствующую авторизацию).

В Bash на сервере, не в контейнере приложения:

```bash
read -r -s -p 'GitHub package read token: ' GHCR_TOKEN
printf '\n'
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io --username EgorArutiunean --password-stdin
unset GHCR_TOKEN
```

Это сохраняет registry credential для Docker этого пользователя. Не добавляйте
токен в DATABASE_URL, код, screenshot или переменные backend. GHCR login на вашем
ноутбуке не даёт серверу доступ. Для публичных образов login не обязателен.

## 5. Переменные окружения

Откройте Environment Variables приложения. Используйте `.env.coolify.example`
как шаблон для нового ресурса. Не вставляйте его поверх переменных существующего
чужого приложения: Developer View может заменить набор настроек.

Обязательные поля:

| Поле | Значение для staging |
|---|---|
| `RELEASE_VERSION` | `v0.1.0-rc.2` |
| `BACKEND_IMAGE` | Полная ссылка `images.backend` из manifest |
| `FRONTEND_IMAGE` | Полная ссылка `images.frontend` из того же manifest |
| `POSTGRES_DB` | `buy_staging` |
| `POSTGRES_USER` | `buy_app` |
| `POSTGRES_PASSWORD` | Новый случайный пароль |
| `DATABASE_URL` | `postgresql+psycopg://buy_app:ПАРОЛЬ@postgres:5432/buy_staging` |
| `AUTH_SECRET_KEY` | Независимый случайный секрет, минимум 32 символа |
| `CORS_ORIGINS` | `https://stage.ВАШ-ДОМЕН` без `/` в конце |
| `SENTRY_ENVIRONMENT` | `staging` |

Сгенерируйте пароль БД и auth secret отдельно командой `openssl rand -hex 32`.
Hex удобен тем, что не требует URL-encoding в DATABASE_URL. При другом формате
пароля спецсимволы в URL нужно percent-encode; в POSTGRES_PASSWORD остаётся исходный
пароль. Не оставляйте `REPLACE_*` из шаблона.

`CORS_ORIGINS` — обычная строка, несколько origins разделяются запятыми.
**Не JSON-массив**: прежний пример в чате с `[...]` был неверен.
`APP_ENV=production` зафиксирован даже для staging: работают строгие security
проверки и запрет demo seed. `VITE_*` здесь не задаём: frontend уже собран с
`/api/v1` и выключенным demo mode. Никакие demo-пароли в этой среде не создаются.

Пароли — runtime secrets. Не передавайте их как Docker build arguments.
Изменение POSTGRES_PASSWORD после первого старта не меняет пароль существующей
роли PostgreSQL; ротацию выполнять отдельно, не удаляя volume.

Пара RC2 опубликована, ссылки находятся в `.env.coolify.example` и
[manifest artifact релизного запуска](https://github.com/EgorArutiunean/faethon-system/actions/runs/38626493169).
RC1 не используйте для новых развёртываний: в его frontend обнаружены
исправляемые HIGH-уязвимости curl/libcurl. RC2 обновляет эти пакеты до
`8.14.1-2+deb13u7`. Подробности: [release evidence RC2](release-rc2-security.md).
Не используйте `latest` и не смешивайте backend/frontend разных manifest.

## 6. Домен и TLS

1. В DNS создайте A-запись `stage` на IP deployment-сервера. AAAA добавляйте
   только при работающих IPv6 и firewall правилах.
2. В Domains приложения выберите сервис **frontend**, протокол HTTPS,
   hostname `stage.ВАШ-ДОМЕН`, внутренний port **8080**.
3. Если интерфейс предоставляет одно поле, значение обычно выглядит как
   `https://stage.ВАШ-ДОМЕН:8080`. Это порт upstream внутри контейнера;
   пользователи открывают `https://stage.ВАШ-ДОМЕН` по стандартному 443.
4. Не назначайте публичные домены postgres, migrate или backend.
5. Убедитесь, что Coolify Proxy запущен и DNS указывает на правильный сервер.

Compose не публикует host ports и не конфликтует с другими приложениями на 80/443.
Внешний путь: Coolify Proxy → frontend nginx:8080 → backend:8000 → postgres:5432.
TLS завершается на Coolify Proxy. Проверяйте реальный HTTPS и HTTP→HTTPS redirect
после запуска; зелёный контейнер сам по себе не подтверждает корректный сертификат.

## 7. Первый Deploy

Сохраните переменные и нажмите Deploy. Ожидаемые результаты:

1. Образы скачаны по заданным digest'ам.
2. `postgres` healthy; создан persistent volume `postgres_data` с префиксом
   Coolify ресурса. Запишите его фактическое имя в release record.
3. `migrate` выполнил `alembic upgrade head` и завершился `Exited (0)`.
4. `backend` healthy, затем `frontend` healthy.

`exclude_from_hc: true` у migrate — специальное поле Coolify для one-shot
контейнеров. Оно исключает завершённый job из общего health, но не отменяет
`service_completed_successfully`: при ошибке миграции новый backend не стартует.
Используйте версию Coolify с поддержкой этого поля. Если интерфейс считает
`Exited (0)` ошибкой или сообщает unknown property, проверьте версию и managed
Compose mode; не убирайте зависимость backend от успешной миграции.

Проверьте с собственного компьютера/внешней машины:

```bash
curl --fail https://stage.ВАШ-ДОМЕН/health/live
curl --fail https://stage.ВАШ-ДОМЕН/health/ready
```

Для RC2 readiness должен вернуть `status=ready` и
`schema_revision=0018_reconcile_model_schema`. Откройте `/login`.
В Coolify Terminal сервиса backend дополнительно выполните `alembic current`.

## 8. Создайте администратора

Первый вход требует bootstrap. В **Terminal контейнера backend** запустите
этот интерактивный Python prompt (email и пароль вводятся после запуска):

```bash
python -c 'import os,getpass,runpy; os.environ["BOOTSTRAP_ADMIN_EMAIL"]=input("Admin email: ").strip(); os.environ["BOOTSTRAP_ADMIN_PASSWORD"]=getpass.getpass("Temporary password (12+ characters): "); runpy.run_path("scripts/bootstrap_admin.py", run_name="__main__")'
```

Пароль не помещается в shell history или постоянные переменные Coolify. Если
getpass предупреждает, что ввод виден, прервите и используйте интерактивный SSH
терминал с `docker exec -it ИМЯ_BACKEND sh`. После создания войдите в UI и смените
временный пароль. Bootstrap не сбрасывает существующий аккаунт.

Свежая база содержит схему и роли, но не рабочие справочники/документы. Создайте
тестовые данные через приложение и разрешённый импорт. `seed_demo.py` при
APP_ENV=production запрещён. Данные legacy с персональной информацией в staging
без минимизации не переносить.

## 9. Проверка после входа

Проверьте через браузер авторизацию, dashboard, создание склада/товара, приход,
продажу, изменения остатков и права тестового пользователя. Выполните сценарии
из `docs/manual-qa-checklist.md` и зафиксируйте результаты UAT.

Для автоматического smoke нужен пользователь с доступом к dashboard, который
уже сменил временный пароль. С доверенной внешней машины с Python 3 и checkout:

```bash
python -c 'import os,getpass,runpy; os.environ["SMOKE_BASE_URL"]=input("HTTPS base URL: ").strip(); os.environ["SMOKE_EMAIL"]=input("Smoke email: ").strip(); os.environ["SMOKE_PASSWORD"]=getpass.getpass("Smoke password: "); runpy.run_path("backend/scripts/release_smoke.py", run_name="__main__")'
```

Ожидается JSON `status=passed`: live, ready, login, me, dashboard отвечают 200.
Этот скрипт проверяет HTTP и учётную запись, но не доказывает identity контейнеров.
В Coolify deployment logs/Deployable Compose сверяйте обе image@sha256 ссылки
с manifest; на сервере можно дополнительно проверить `docker inspect`:

```bash
docker inspect --format '{{.Config.Image}}' ИМЯ_BACKEND
docker inspect --format '{{.Config.Image}}' ИМЯ_FRONTEND
```

Сохраните: Coolify version, UUID ресурса, commit Compose, version/SHA из manifest,
две image references, revision схемы, timestamp, deployment ID, smoke result,
volume name и решение UAT. Пароли/токены в release record не включать.

## 10. Backup до эксплуатации

База находится в named volume, переживающем redeploy. Снимок VPS не заменяет
проверенный PostgreSQL dump и offsite-копию. Не включайте prune unused volumes
и не удаляйте ресурс вместе с volumes ради исправления запуска.

Скрипт `scripts/backup_postgres.sh` умеет находить PostgreSQL по Compose labels,
поэтому ему не нужен секретный env-файл Coolify. На deployment-сервере выясните
реальный project name, а не предполагайте, что он равен `buy-modern-staging`:

```bash
docker ps --filter label=com.docker.compose.service=postgres --format '{{.Names}}'
docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' ИМЯ_НУЖНОГО_POSTGRES
```

Используйте проверенный checkout репозитория на сервере и отдельную директорию:

```bash
umask 077
BACKUP_COMPOSE_PROJECT=ФАКТИЧЕСКИЙ_PROJECT BACKUP_DIR=/var/backups/buy-staging BACKUP_RETENTION_DAYS=0 sh scripts/backup_postgres.sh
```

Для первого запуска retention=0 отключает удаление старых dump. Скрипт должен
создать `.dump` и `.sha256`, успешно проверить `pg_restore --list`. Затем настройте
таймер и offsite по `docs/backup-operations.md`. Проведите restore в отдельную БД,
проверьте логин и контрольные итоги. Не восстанавливайте тестовый dump поверх live DB.

## 11. Обновление RC и production

1. Изменения приложения проходят CI на `main`.
2. Запустите `Publish release candidate` с **новой** version (после RC2 — RC3),
   полным source SHA и `delivery=coolify-manual`; `promote_to_production=false`.
3. Скачайте новый release manifest после успешного publish. Не перезапускайте
   публикацию под уже использованной версией: version tags реестра технически
   перезаписываемы; неизменяемую identity дают только digest'ы.
4. Сделайте backup и запишите прежнюю пару образов, version, revision схемы.
5. В staging Coolify обновите **вместе** BACKEND_IMAGE, FRONTEND_IMAGE,
   RELEASE_VERSION из одного manifest; нажмите Deploy, а не только Restart.
6. Проверьте успешную миграцию, фактические образы, внешний smoke и UAT.
7. Для production создайте отдельное Application с тем же Compose, новым доменом,
   собственной БД/volume/секретами и SENTRY_ENVIRONMENT=production. После backup,
   бизнес-приёмки и явного GO перенесите ту же проверенную пару digest'ов из staging.

Compose redeploy может давать краткий downtime; zero-downtime здесь не обещается.
Изменения схемы должны учитывать ещё работающий старый backend; несовместимые
миграции требуют окна обслуживания и остановки пользовательских записей.
Автоматический production approval из старого GitHub job не защищает ручной
Deploy в Coolify: ограничьте доступ к production и фиксируйте решение оператора.

## 12. Откат

Для отката приложения к предыдущей паре образов нужна проверенная совместимость
с **текущей** БД. Поддерживаемый простой случай: у прошлого образа та же Alembic
head, что и у текущей БД, и подтверждена совместимость данных.

1. Остановите пользовательские операции; сохраните backup и сведения об ошибке.
2. Проверьте `alembic current` в текущем backend и `alembic heads` в предыдущем
   backend-образе (одноразовый `docker run --rm IMAGE@sha256:... alembic heads`).
3. Только при совпадении и подтверждённой совместимости верните прежние
   BACKEND_IMAGE, FRONTEND_IMAGE и RELEASE_VERSION в Coolify, затем Deploy.
   One-shot `upgrade head` на той же revision ничего не меняет.
4. Повторите проверку image identity, readiness, login и smoke.

Если revisions различаются, не запускайте старый Compose вслепую: старая версия
Alembic может не знать новую revision, а readiness отклонит несовпадение.
Выберите исправление вперёд либо отдельное восстановление проверенного backup
с согласованной потерей записей после backup. Автоматический downgrade БД не предусмотрен.
Кнопка rollback исходного commit в Coolify не гарантирует возврат переменных
image digest: сверяйте их вручную.

## 13. Типовые проблемы

| Симптом | Что проверить |
|---|---|
| `unauthorized` при pull | Видимость GHCR package, read:packages, login правильного пользователя на deployment-сервере |
| `no matching manifest` | AMD64 сервера и архитектуру образа |
| `port is already allocated` | Загружен coolify Compose, нет host ports для 80/443/5432 |
| `migrate Exited (1)` | Его лог, DATABASE_URL, пароль роли, состояние Alembic; backend должен остаться заблокирован |
| `migrate Exited (0)` | Нормальный итог job; нужен exclude_from_hc в поддерживаемой версии Coolify |
| `No available server` | DNS, TLS, домен frontend:8080, proxy network, оба healthchecks |
| Backend падает на CORS | HTTPS строка без JSON-скобок и без wildcard |
| DB password не совпадает после смены env | Существующий volume хранит прежний пароль роли; env не выполняет ALTER ROLE |
| Не пускает с demo-паролем | Выполнить bootstrap и обязательную смену пароля |
| Pull успешен, smoke не проходит | Проверить публичный маршрут, учётную запись и revision; это не успешный релиз |

## 14. Что уже проверено и чеклист первого запуска

Локально 2026-10-14 проверены: синтаксис workflows (actionlint), ограничения
Coolify Compose и его стандартная часть (`docker compose config`), запуск на
PostgreSQL 16 с локально собранными RC1-образами. Bootstrap, смена пароля и smoke
дали 200 для live/ready/login/me/dashboard, revision `0018_reconcile_model_schema`.
После удаления и повторного создания контейнеров и сети аккаунт сохранился в
volume. Намеренная ошибка migration job не позволила стартовать backend/frontend.
Тестовые ресурсы удалены. Это **не** проверка опубликованных GHCR digest'ов,
Coolify parser, целевого сервера или внешнего HTTPS.

Повторить конфигурационную проверку (Python 3 + Docker Compose):

```bash
python -m pip install PyYAML==6.0.3
python scripts/check_coolify_compose.py
```

Для полного локального smoke сначала скачайте нужную пару образов, затем:

```bash
python scripts/smoke_coolify_compose.py --backend-image 'BACKEND_IMAGE@sha256:...' --frontend-image 'FRONTEND_IMAGE@sha256:...'
```

Замените placeholders полными ссылками из manifest. Скрипт не собирает образы и
не выполняет pull: PostgreSQL-образ из Compose также должен быть скачан заранее.
Он создаёт уникальный project `buy-coolify-smoke-*`, случайные тестовые секреты и
порт только на 127.0.0.1. По завершении удаляет **собственный** тестовый volume;
не используйте его для работы с production-данными.

Чеклист оператора:

- [ ] Commit с Coolify-конфигурацией опубликован в GitHub; CI зелёный.
- [ ] Записаны версия Coolify, сервер, свободные ресурсы и architecture.
- [ ] Создано staging Application; Compose managed; auto-deploy выключен.
- [ ] Записаны config commit, release manifest и пара image digest'ов.
- [ ] Секреты заменены; origin, DNS и frontend:8080 настроены.
- [ ] Deploy завершён; migrate Exited (0); три сервиса healthy.
- [ ] HTTPS и redirect проверены с внешней машины.
- [ ] Admin создан; временный пароль заменён; внешний smoke прошёл.
- [ ] Backup, offsite и восстановление в изолированную БД проверены.
- [ ] UAT выполнен; решение о production GO/NO-GO записано.

### RC2 и первый staging (2026-10-15)

RC2 прошёл полный CI и проверку публикуемых образов до push. Оператор сообщил
об успешном деплое, замене ссылок образов, создании администратора и входе.
После проверенного backup и изолированного restore drill оператор выполнил
`Redeploy`: deployment `2026-10-15 11:00:05–11:00:56 UTC` завершился `Success`.
На Compose project `l4w4kssko4ogk00sg8co480s` контейнеры frontend, backend и
PostgreSQL находятся в `healthy`. `docker inspect` подтвердил exact RC2 image
references из [release evidence RC2](release-rc2-security.md), включая
`frontend@sha256:a031a649a9987dd8cd8b7417faf6c893e2228390d43707a565616bd68b3722b6`
и `backend@sha256:b88a592827ec5cb55270ac7a54336eb939418289ab34703db5f346cd2de49622`.
После повторного деплоя внешняя HTTPS-проверка 2026-10-15 в 11:07 UTC вернула
200 для `/health/live`, `/health/ready` и `/login`, database=ok,
revision `0018_reconcile_model_schema`. Проверка TLS-сертификата не отключалась.
HTTP `/login` перенаправляется на HTTPS (307); HTTPS-ответ содержит HSTS,
CSP, X-Content-Type-Options, X-Frame-Options и прочие настроенные security headers.
Оператор отдельно подтвердил `ready/database=ok/revision=0018` через браузер.
После обновления оператор также подтвердил вход прежним администратором и работу
панели управления; автоматический `release_smoke.py` после Redeploy ещё не запускался.
Остаются полный авторизованный smoke, UAT и offsite-копия; healthy-контейнеры и
image identity не заменяют этих проверок.
Для следующего шага подготовлен [отдельный staging backup timer](staging-backup-timer.md).

## Источники

- [Coolify Docker Compose](https://coolify.io/docs/applications/builds/docker-compose)
- [GitHub Actions и готовые образы](https://coolify.io/docs/applications/sources/github/actions)
- [Домены и внутренние порты](https://coolify.io/docs/core/networking/domains)
- [Переменные окружения](https://coolify.io/docs/applications/configuration/environment-variables)
- [Deploy webhooks](https://coolify.io/docs/core/automation/deploy-webhooks)
- [Backup приложения](backup-operations.md)
