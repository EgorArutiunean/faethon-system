# PostgreSQL restore drill — 2026-10-12

## Scope

Локальная production-readiness репетиция восстановления PostgreSQL. Рабочая
локальная БД использовалась только как источник `pg_dump`; восстановление
выполнялось в отдельную БД `buy_modern_restore_drill_20261012`.

## Backup evidence

- формат: PostgreSQL custom dump (`pg_dump -Fc`);
- размер: `129908` bytes;
- SHA-256: `778ca5df9d4d91345190b8a898b5d55b8451a3e948346ff46d37800d4c2f00b5`;
- `pg_restore --list`: passed;
- атомарная запись и checksum sidecar: passed;
- измеренное время непосредственного restore: `1.03 s`.

Backup-файл и checksum являются локальными ignored runtime artifacts и не
включаются в Git.

## Reconciliation

Контрольные значения исходной и восстановленной БД совпали:

| Контроль | Значение |
|---|---:|
| Alembic revision | `0018_reconcile_model_schema` |
| Products | 375 |
| Warehouses | 3 |
| Partners | 4 |
| Documents / total | 3 / 547.00 |
| Payments / total | 3 / 80.00 |
| Stock rows / quantity | 376 / 12908.600 |
| Cash operations / amount | 4 / 105.00 |
| Users | 5 |

## Application smoke on restored database

- `/health/ready`: HTTP `200`;
- demo authentication: passed;
- authenticated `/api/v1/dashboard/summary`: passed;
- временный API запускался только поверх восстановленной копии.

## Result and limitations

`DR-10` и `DR-11` подтверждены локально. Drill обнаружил и исправил Windows
quoting defect в PowerShell backup/restore scripts. `DR-12` остаётся открытым:
RPO зависит от ещё не настроенного расписания/offsite retention, а RTO должно
быть повторно измерено на целевой staging/production инфраструктуре и принято
бизнес-владельцем.
