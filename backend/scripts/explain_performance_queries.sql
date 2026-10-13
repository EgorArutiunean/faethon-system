\set ON_ERROR_STOP on
\pset pager off
\timing on

DO $$
BEGIN
    IF current_database() !~ '_perf$' THEN
        RAISE EXCEPTION 'Refusing to profile non-performance database: %', current_database();
    END IF;
END
$$;

\echo 'Q1 product page: group filter and name order'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT id, sku, name, group_id, unit_id, base_price, is_active, created_at, updated_at
FROM products
WHERE group_id IN (10, 20, 30)
ORDER BY name, id
LIMIT 25 OFFSET 250;

\echo 'Q2 product lookup: infix name/SKU search'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT id, sku, name, group_id, unit_id, base_price, is_active
FROM products
WHERE is_active IS TRUE
  AND (name ILIKE '%0199%' OR sku ILIKE '%0199%')
ORDER BY name, id
LIMIT 50;

\echo 'Q3 latest incoming purchase cost for visible products'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT *
FROM (
    SELECT
        dl.product_id,
        dl.price AS purchase_cost,
        d.id AS document_id,
        d.number AS document_number,
        d.document_date,
        row_number() OVER (
            PARTITION BY dl.product_id
            ORDER BY d.document_date DESC, d.id DESC, dl.id DESC
        ) AS purchase_rank
    FROM document_lines AS dl
    JOIN documents AS d ON d.id = dl.document_id
    WHERE d.document_type = 'incoming'
      AND d.status = 'posted'
      AND dl.product_id = ANY (ARRAY[101, 102, 103, 104, 105, 106, 107, 108, 109, 110,
                                     111, 112, 113, 114, 115, 116, 117, 118, 119, 120,
                                     121, 122, 123, 124, 125])
) AS ranked
WHERE purchase_rank = 1;

\echo 'Q4 partner page: type filter and name order'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT id, name, code, phone, partner_type, is_active, created_at, updated_at
FROM partners
WHERE partner_type = 'customer'
ORDER BY name, id
LIMIT 25 OFFSET 250;

\echo 'Q5 partner lookup: infix name/code/phone search'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT id, name, code, phone, partner_type, is_active
FROM partners
WHERE is_active IS TRUE
  AND (name ILIKE '%0999%' OR code ILIKE '%0999%' OR phone ILIKE '%0999%')
ORDER BY name, id
LIMIT 50;

\echo 'Q6 document page: type/status and newest first'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT d.*
FROM documents AS d
LEFT JOIN partners AS p ON p.id = d.partner_id
WHERE d.document_type = 'outgoing'
  AND d.status = 'posted'
ORDER BY d.document_date DESC, d.id DESC
LIMIT 25 OFFSET 250;

\echo 'Q7 document search: number or partner name'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT d.*
FROM documents AS d
WHERE d.id IN (
    SELECT matched.id
    FROM (
        SELECT d1.id
        FROM documents AS d1
        WHERE d1.number ILIKE '%00999%'
        UNION
        SELECT d2.id
        FROM documents AS d2
        JOIN partners AS p ON p.id = d2.partner_id
        WHERE p.name ILIKE '%00999%'
    ) AS matched
)
ORDER BY d.document_date DESC, d.id DESC
LIMIT 25;

\echo 'Q8 partner document balances for one visible page'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT partner_id,
       coalesce(sum(CASE
           WHEN status = 'posted' AND document_type = 'outgoing' THEN total_amount
           WHEN status = 'posted' AND document_type = 'incoming' THEN -total_amount
           ELSE 0
       END), 0) AS balance
FROM documents
WHERE partner_id = ANY (ARRAY[1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
                              11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
                              21, 22, 23, 24, 25])
GROUP BY partner_id;

\echo 'Q9 partner payment balances for one visible page'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT partner_id,
       coalesce(sum(CASE
           WHEN status = 'posted' AND payment_type = 'customer_payment' THEN -amount
           WHEN status = 'posted' AND payment_type IN ('supplier_payment', 'refund') THEN amount
           ELSE 0
       END), 0) AS balance
FROM payments
WHERE partner_id = ANY (ARRAY[1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
                              11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
                              21, 22, 23, 24, 25])
GROUP BY partner_id;

\echo 'Q10 dashboard document aggregate for the last year'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT document_type, status, count(*), sum(total_amount)
FROM documents
WHERE document_date >= current_date - 365
GROUP BY document_type, status;

\echo 'Q11 dashboard recent documents'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT *
FROM documents
WHERE document_date >= current_date - 365
ORDER BY document_date DESC, id DESC
LIMIT 6;

\echo 'Q12 cash total and current balance'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT count(id),
       coalesce(sum(CASE
           WHEN status = 'cancelled' THEN 0
           WHEN operation_type = 'cash_in' THEN amount
           WHEN operation_type = 'cash_out' THEN -amount
           WHEN operation_type = 'correction' AND direction = 'out' THEN -amount
           WHEN operation_type = 'correction' THEN amount
           ELSE 0
       END), 0) AS current_balance
FROM cash_operations;

\echo 'Q13 cash book deep page'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT *
FROM cash_operations
ORDER BY operation_date DESC, id DESC
LIMIT 25 OFFSET 50000;

\echo 'Q14 stock totals by warehouse'
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, SUMMARY)
SELECT w.name, sum(sb.quantity) AS quantity
FROM warehouses AS w
JOIN stock_balances AS sb ON sb.warehouse_id = w.id
GROUP BY w.id, w.name
ORDER BY quantity DESC, w.name
LIMIT 5;
