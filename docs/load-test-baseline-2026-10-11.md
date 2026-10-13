# Endpoint load-test baseline — 2026-10-11

## Method

The concurrent test used the migrated `buy_modern_perf` PostgreSQL database and
the synthetic volume documented in `performance-baseline-2026-10-11.md`.
Requests passed through the real FastAPI routes, authentication dependencies,
Pydantic response serialization, SQLAlchemy sessions and PostgreSQL queries via
HTTPX ASGI transport.

This is a local application/database baseline. It does not include nginx, TLS,
container networking or a production-sized remote host, so production approval
still requires the same workload to be repeated on staging.

The guarded runner is `backend/scripts/load_test.py`. It refuses to run unless
the configured database name ends with `_perf` and requires credentials through
`LOAD_TEST_EMAIL` and `LOAD_TEST_PASSWORD`.

## Workloads and SLO

| Profile | Concurrency | Requests | Scenarios | SLO |
| --- | ---: | ---: | --- | ---: |
| Regular operations | 12 | 480 | Product/partner/document search, scoped debts, Dashboard, deep cash page | p95 <= 2 s |
| Reports | 4 | 80 | Documents register, cash book, partner debts, warehouse stock balances | p95 <= 5 s |

Every endpoint was warmed once before measurements. The control run doubled the
initial sample so each regular scenario had 80 observations and each report had
20 observations.

## Control-run result

### Regular operations

- throughput: **36.66 requests/second**;
- errors: **0%**;
- overall p50: **287 ms**;
- overall p95: **580 ms**;
- overall p99: **638 ms**;
- result: **PASS** against the 2-second p95 SLO.

| Scenario | p95 | p99 |
| --- | ---: | ---: |
| Product search | 363 ms | 411 ms |
| Partner search | 301 ms | 327 ms |
| Document search | 340 ms | 368 ms |
| Balances for 25 partners | 325 ms | 366 ms |
| Dashboard summary | 638 ms | 685 ms |
| Cash page at offset 50,000 | 401 ms | 463 ms |

### Reports

- throughput: **2.10 requests/second**;
- errors: **0%**;
- overall p50: **952 ms**;
- overall p95: **5.51 s**;
- overall p99: **6.00 s**;
- result: **FAIL** against the 5-second p95 SLO.

| Scenario | Rows represented by filter | p95 | p99 | Result |
| --- | ---: | ---: | ---: | --- |
| Documents register, 10 days | about 1,500 | 1.34 s | 1.37 s | PASS |
| Cash book, 10 days | about 1,500 | 1.16 s | 1.67 s | PASS |
| Customer debts | about 3,300 partners | 1.32 s | 1.59 s | PASS |
| Stock balances, one warehouse | 20,000 | 5.73 s | 6.00 s | **FAIL** |

## Finding and follow-up

`PERF-09` is complete as a reproducible local concurrent baseline, and
`PERF-10` passes for regular operations. The initial failure isolated the
stock-balance response: returning and serializing all 20,000 rows dominated
the route even though the database query itself was about 39 ms.

## Post-pagination verification

`PERF-11` added bounded server-side stock-report pages and calculates the exact
row count and full filtered quantity total in SQL. The UI requests 25 rows per
page. The separate export route still requests the complete filtered dataset.

The same workload was repeated after the change:

- regular operations: **480 requests**, concurrency **12**, **0%** errors,
  p50 **642 ms**, p95 **1.46 s**, p99 **1.86 s** — **PASS** against 2 seconds;
- reports: **80 requests**, concurrency **4**, **0%** errors, p50 **731 ms**,
  p95 **1.41 s**, p99 **1.88 s** — **PASS** against 5 seconds;
- stock balances specifically: p50 **299 ms**, p95 **545 ms**, p99 **731 ms**.

The stock-report p95 improved from **5.73 s** to **545 ms** (about 10.5x), and
the combined report profile improved from **5.51 s** to **1.41 s**. `PERF-11`
is complete for the local baseline. Production approval still requires this
same runner against staging through nginx/TLS and production-sized resources.
