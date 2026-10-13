\set ON_ERROR_STOP on

DO $$
BEGIN
    IF current_database() !~ '_perf$' THEN
        RAISE EXCEPTION 'Refusing to seed non-performance database: %', current_database();
    END IF;
END
$$;

TRUNCATE TABLE
    product_groups,
    units,
    warehouses,
    products,
    partners,
    documents,
    payments,
    cash_operations,
    stock_balances
RESTART IDENTITY CASCADE;

INSERT INTO product_groups (name, created_at, updated_at)
SELECT 'Group ' || value, now(), now()
FROM generate_series(1, 100) AS value;

INSERT INTO units (name, short_name, created_at, updated_at)
VALUES ('Piece', 'pc', now(), now());

INSERT INTO warehouses (code, name, created_at, updated_at)
SELECT 'WH-' || lpad(value::text, 2, '0'), 'Warehouse ' || value, now(), now()
FROM generate_series(1, 10) AS value;

INSERT INTO products (sku, name, group_id, unit_id, base_price, is_active, created_at, updated_at)
SELECT
    'SKU-' || lpad(value::text, 6, '0'),
    'Product ' || lpad(value::text, 6, '0'),
    ((value - 1) % 100) + 1,
    1,
    (10 + (value % 1000))::numeric(14, 2),
    value % 20 <> 0,
    now() - ((value % 730) || ' days')::interval,
    now()
FROM generate_series(1, 20000) AS value;

INSERT INTO partners (name, code, phone, partner_type, is_active, created_at, updated_at)
SELECT
    'Partner ' || lpad(value::text, 6, '0'),
    'PART-' || lpad(value::text, 6, '0'),
    '+373' || lpad(value::text, 8, '0'),
    CASE value % 3 WHEN 0 THEN 'customer' WHEN 1 THEN 'supplier' ELSE 'both' END,
    value % 25 <> 0,
    now() - ((value % 730) || ' days')::interval,
    now()
FROM generate_series(1, 10000) AS value;

INSERT INTO documents (
    document_type,
    number,
    document_date,
    status,
    partner_id,
    warehouse_id,
    total_amount,
    currency_code,
    exchange_rate,
    foreign_total_amount,
    posting_version,
    created_at,
    updated_at
)
SELECT
    CASE value % 4
        WHEN 0 THEN 'incoming'
        WHEN 1 THEN 'outgoing'
        WHEN 2 THEN 'adjustment'
        ELSE 'transfer'
    END,
    'DOC-' || lpad(value::text, 8, '0'),
    current_date - (value % 730),
    CASE WHEN value % 10 = 0 THEN 'draft' ELSE 'posted' END,
    ((value - 1) % 10000) + 1,
    ((value - 1) % 10) + 1,
    (100 + (value % 10000))::numeric(14, 2),
    'RUB_PMR',
    1,
    (100 + (value % 10000))::numeric(14, 2),
    CASE WHEN value % 10 = 0 THEN 0 ELSE 1 END,
    now() - ((value % 730) || ' days')::interval,
    now()
FROM generate_series(1, 100000) AS value;

INSERT INTO document_lines (
    document_id,
    product_id,
    quantity,
    price,
    line_total,
    created_at,
    updated_at
)
SELECT
    document_id,
    ((document_id * 3 + line_number - 1) % 20000) + 1,
    line_number::numeric(14, 3),
    (10 + (document_id % 1000))::numeric(14, 2),
    (line_number * (10 + (document_id % 1000)))::numeric(14, 2),
    now(),
    now()
FROM generate_series(1, 100000) AS document_id
CROSS JOIN generate_series(1, 3) AS line_number;

INSERT INTO payments (
    partner_id,
    document_id,
    payment_date,
    amount,
    method,
    payment_type,
    status,
    created_at,
    updated_at
)
SELECT
    ((value - 1) % 10000) + 1,
    value,
    current_date - (value % 730),
    (50 + (value % 5000))::numeric(14, 2),
    CASE WHEN value % 2 = 0 THEN 'cash' ELSE 'bank' END,
    CASE WHEN value % 3 = 0 THEN 'supplier_payment' ELSE 'customer_payment' END,
    CASE WHEN value % 20 = 0 THEN 'cancelled' ELSE 'posted' END,
    now() - ((value % 730) || ' days')::interval,
    now()
FROM generate_series(1, 80000) AS value;

INSERT INTO cash_operations (
    operation_date,
    direction,
    amount,
    partner_id,
    status,
    operation_type,
    created_at,
    updated_at
)
SELECT
    current_date - (value % 730),
    CASE WHEN value % 3 = 0 THEN 'out' ELSE 'in' END,
    (10 + (value % 1000))::numeric(14, 2),
    ((value - 1) % 10000) + 1,
    CASE WHEN value % 25 = 0 THEN 'cancelled' ELSE 'posted' END,
    CASE WHEN value % 3 = 0 THEN 'cash_out' ELSE 'cash_in' END,
    now() - ((value % 730) || ' days')::interval,
    now()
FROM generate_series(1, 100000) AS value;

INSERT INTO stock_balances (product_id, warehouse_id, quantity, created_at, updated_at)
SELECT
    product_id,
    warehouse_id,
    ((product_id + warehouse_id) % 500)::numeric(14, 3),
    now(),
    now()
FROM generate_series(1, 20000) AS product_id
CROSS JOIN generate_series(1, 5) AS warehouse_id;

ANALYZE;

SELECT relname AS table_name, n_live_tup AS estimated_rows
FROM pg_stat_user_tables
WHERE relname IN (
    'products', 'partners', 'documents', 'document_lines',
    'payments', 'cash_operations', 'stock_balances'
)
ORDER BY relname;
