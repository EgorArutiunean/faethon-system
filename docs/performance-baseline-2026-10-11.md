# PostgreSQL performance baseline — 2026-10-11

## Scope and method

Baseline recorded on local PostgreSQL 16 in the isolated `buy_modern_perf`
database. No production or developer data was modified. The database was
migrated from an empty schema to `0016_token_revocation` and populated with
deterministic synthetic data:

| Entity | Rows |
| --- | ---: |
| Products | 20,000 |
| Partners | 10,000 |
| Documents | 100,000 |
| Document lines | 300,000 |
| Payments | 80,000 |
| Cash operations | 100,000 |
| Stock balances | 100,000 |

The measurements are warm-cache, single-run SQL execution times from
`EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)`. They are not HTTP latency or a
concurrent load test and therefore do not close `PERF-09..11`.

Reproduction artifacts:

- `backend/scripts/seed_performance_data.sql` — guarded seed; refuses to run
  unless the database name ends with `_perf`;
- `backend/scripts/explain_performance_queries.sql` — read-only plans for the
  main registries, dashboard aggregates, balances and cash book.

## Baseline results

| Query | Time | Relevant plan observation |
| --- | ---: | --- |
| Product page by groups | 3.4 ms | Sequential scan of 20k products plus top-N sort |
| Product infix lookup | 16.3 ms | Sequential scan; B-tree cannot serve `%term%` |
| Latest purchase cost for 25 products | 18.2 ms | Parallel scan of 300k document lines |
| Partner page by type | 3.2 ms | Existing partner-type index, then top-N sort |
| Partner infix lookup | 12.9 ms | Sequential scan of 10k partners |
| Document page by type/status | 21.7 ms | Sequential scan of 100k documents plus sort |
| Document number/partner infix search | 123.6 ms | Full document/partner scans, hash join and sort |
| Document balances for 25 partners | 10.4 ms | Scans all 100k documents |
| Payment balances for 25 partners | 7.9 ms | Scans all 80k payments |
| Dashboard document aggregate, one year | 24.5 ms | Scans the qualifying half of documents |
| Dashboard recent documents | 20.6 ms | Parallel scan plus top-N sort |
| Cash exact total/current balance | 19.4 ms | Expected full aggregate scan of 100k operations |
| Cash page at offset 50,000 | 85.0 ms | External merge sort, 7.2 MiB temporary file |
| Stock totals by warehouse | 39.3 ms | Expected full aggregate of 100k balances |

All measured SQL statements remain below one second on this local dataset, but
the plans show linear scans and disk sorting that will not scale proportionally.
The current measurements therefore support demo/UAT only, not the production
SLO acceptance criteria.

## Index work (`PERF-08`)

Migration `0017_performance_indexes` implements the candidates justified by the
baseline plans:

1. `document_lines(product_id)` for latest purchase-cost lookup.
2. `documents(document_type, status, document_date DESC, id DESC)` for registry
   pages and `documents(document_date DESC, id DESC)` for the recent feed.
3. `documents(partner_id)` and `payments(partner_id)` for page-scoped debt
   aggregates.
4. `cash_operations(operation_date DESC, id DESC)` for cash-book ordering.
5. `products(group_id, name, id)` and `partners(partner_type, name, id)` for
   filtered registries.
6. PostgreSQL `pg_trgm` GIN indexes for the existing infix product, partner and
   document searches. Plain B-tree indexes do not optimize `%term%`.

The document number/partner search was also rewritten as the union of two
indexed result sets. A cross-table `OR` forced PostgreSQL to scan and join the
complete registries even after the indexes existed.

### Before / after

Both measurements use the same database and row counts. Times are individual
warm-cache `EXPLAIN ANALYZE` executions and should be read as plan evidence,
not as formal latency percentiles.

| Query | Before | After | Result |
| --- | ---: | ---: | --- |
| Product page by groups | 3.4 ms | 3.2 ms | Group index used; small dataset remains cache-bound |
| Product infix lookup | 16.3 ms | 0.4 ms | About 41x faster |
| Latest purchase cost | 18.2 ms | 1.1 ms | About 17x faster |
| Partner page by type | 3.2 ms | 0.42 ms | About 8x faster |
| Partner infix lookup | 12.9 ms | 0.19 ms | About 68x faster |
| Document page by type/status | 21.7 ms | 0.68 ms | About 32x faster |
| Document number/partner search | 123.6 ms | 2.1 ms | About 59x faster after indexed-union rewrite |
| Document balances, 25 partners | 10.4 ms | 0.39 ms | About 27x faster |
| Payment balances, 25 partners | 7.9 ms | 0.23 ms | About 34x faster |
| Dashboard recent documents | 20.6 ms | 0.03 ms | Ordered index stops after six rows |
| Cash page at offset 50,000 | 85.0 ms | 21.9 ms | Disk sort removed; deep offset still scans 50k entries |

The broad dashboard, exact cash-balance and whole-stock aggregates remain near
their baseline because they intentionally process a large fraction of each
table. This validates the earlier conclusion that summary storage, rather than
additional ordinary indexes, is the next option if those queries exceed SLO.

Exact total/current-cash and whole-stock aggregates inherently read broad data
ranges. If production volumes make them exceed SLO after indexing, use summary
tables/materialized counters rather than adding ineffective indexes.

Offset pagination still walks preceding index entries. The proposed cash index
removes the external sort, but cursor/keyset pagination should replace deep
offsets if the cash ledger grows into millions of rows.

## Schema drift finding and resolution

`alembic upgrade head` succeeded on the empty PostgreSQL database, but
`alembic check` failed immediately afterwards. The model metadata expects many
indexes and nullability changes that are absent from the migration chain,
including the same `document_lines.product_id`, document date/type/status,
partner name, payment partner/date and cash operation-date indexes exposed by
the plans.

`PERF-08` therefore used an explicit reviewed migration and matching model
metadata rather than bundling unrelated changes into the performance work.
`CICD-04` subsequently resolved the remaining drift in
`0018_reconcile_model_schema`: legacy nullable values are backfilled before
constraints are tightened, missing indexes are created, and existing unique
constraints are preserved in ORM metadata instead of being replaced.

The migration passed on the populated performance database, including
`0018 -> 0017 -> 0018`, and on a clean PostgreSQL database upgraded from the
previous release head `0013 -> head`. Both paths now finish with
`No new upgrade operations detected` from `alembic check`.

## Acceptance status

- `PERF-07`: complete — reproducible PostgreSQL plans and baseline recorded.
- `PERF-08`: complete — reviewed migration, indexed search rewrite, repeat plans
  and before/after evidence recorded; downgrade/upgrade cycle passed.
- `PERF-09`: complete as a local endpoint-level concurrent baseline; staging
  repetition remains a production release gate.
- `PERF-10`: complete for the defined baseline (`p95 580 ms`, zero errors).
- `PERF-11`: complete for the local baseline; the stock-balance report now
  returns bounded pages with exact SQL count/quantity totals. Its p95 improved
  from `5.73 s` to `545 ms`, and the combined report p95 improved from
  `5.51 s` to `1.41 s` with zero errors. Staging nginx/TLS repetition remains
  a production release gate.
