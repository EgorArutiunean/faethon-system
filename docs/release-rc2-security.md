# RC2: security refresh и staging evidence

Обновлено: 2026-10-15 (Europe/Chisinau).

## Identity и публикация

- Version: `v0.1.0-rc.2`.
- Source SHA: `3f150991e334540643c2b6c5be562bba6087fbed`.
- [CI: success](https://github.com/EgorArutiunean/faethon-system/actions/runs/38625977948).
- [Publish: success](https://github.com/EgorArutiunean/faethon-system/actions/runs/38626493169).
- Manifest artifact: `release-manifest-v0.1.0-rc.2`, ID `11924800090`.
- Security artifact: `release-security-reports-v0.1.0-rc.2`, ID `11924436409`.
- Manifest built_at: `2026-10-14T19:48:36Z` (UTC, как в артефакте).
- Database revision: `0018_reconcile_model_schema`, без изменений относительно RC1.
- Delivery: `coolify-manual`; staging и production jobs workflow пропущены.

```dotenv
RELEASE_VERSION=v0.1.0-rc.2
BACKEND_IMAGE=ghcr.io/egorarutiunean/faethon-system-backend@sha256:b88a592827ec5cb55270ac7a54336eb939418289ab34703db5f346cd2de49622
FRONTEND_IMAGE=ghcr.io/egorarutiunean/faethon-system-frontend@sha256:a031a649a9987dd8cd8b7417faf6c893e2228390d43707a565616bd68b3722b6
```

Менять эти три поля вместе. Пароли и DATABASE_URL остаются прежними при
обновлении существующего ресурса. Не удалять database volume.

## Исправление и проверки

[Предыдущий CI](https://github.com/EgorArutiunean/faethon-system/actions/runs/38620751213)
заблокировал frontend по CVE-2026-8286 и CVE-2026-8927: curl/libcurl версии
`8.14.1-2+deb13u5`. В Dockerfile.prod закреплены исправленные пакеты Debian
`curl=8.14.1-2+deb13u7` и `libcurl4t64=8.14.1-2+deb13u7`.

- [x] Локальная production-сборка; установленные версии пакетов подтверждены.
- [x] Локальный Trivy: нет исправляемых HIGH/CRITICAL; security gate не отключён.
- [x] Полный CI: backend, frontend, PostgreSQL integrity, real E2E, CodeQL,
  dependency audit, actionlint/Compose и container supply-chain — success.
  PR-only dependency-review закономерно skipped для main push.
- [x] В release workflow проверены именно публикуемые backend/frontend images,
  без rebuild между scan и push. Ignore-unfixed соответствует политике CI;
  результат не означает отсутствия всех возможных уязвимостей.
- [x] Опубликованные образы скачаны из GHCR по указанным digest'ам.
- [x] Изолированный smoke на этой точной паре: миграция, nginx routing,
  bootstrap, смена пароля, live/ready/login/me/dashboard — passed.
- [x] После пересоздания контейнеров/сети тестовый аккаунт сохранился в volume.
- [x] Намеренный exit=7 migration job блокирует backend/frontend.
- [x] Только созданные тестовые контейнеры, сеть и volume удалены после проверки.

## Целевой staging: разделение фактов

- Оператор сообщил об успешном deploy, замене ссылок образов, создании admin
  и успешном входе. Агент не выполнял remote deploy и не получал пароли.
- Независимо проверены HTTPS GET `/health/live` и `/health/ready`: оба 200,
  status=alive/ready, database=ok, schema_revision=`0018_reconcile_model_schema`.
  Проверка выполнялась без отключения проверки TLS-сертификата.
- Фактические digest'ы запущенных контейнеров пока не сверены независимо.
- Полный авторизованный smoke на staging, UAT, backup/offsite/restore и
  production GO остаются отдельными этапами. Публичная доступность и первый
  вход не являются production-приёмкой.

Адрес staging и секреты намеренно не включены в публичный release record.
