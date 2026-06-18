# Data Preparation

This folder contains controlled one-off tools that prepare old program exports into Buy Modern standard Import Lite templates.

These tools are not part of the web application runtime. The web app keeps one stable import contract; old source files are normalized before upload.

## Legacy Price List

`prepare_legacy_price_list.py` reads a known old price-list XLSX shape and writes:

- `products.xlsx` with Buy Modern columns `sku`, `name`, `category`, `base_price`, `description`, `legacy_name`;
- `opening-stock.xlsx` with Buy Modern columns `product_sku`, `product_name`, `warehouse_name`, `quantity`.

Usage:

```powershell
cd C:\Users\Egor\Buy\buy-modern
python migration\data_preparation\prepare_legacy_price_list.py `
  --input E:\primer.xlsx `
  --output-dir migration\prepared_imports\run-YYYY-MM-DD `
  --warehouse-name "MAIN"
```

Optional category map:

```csv
legacy_name,category
"Old product name, with comma",Category name
```

```powershell
python migration\data_preparation\prepare_legacy_price_list.py `
  --input E:\primer.xlsx `
  --output-dir migration\prepared_imports\run-YYYY-MM-DD `
  --warehouse-name "MAIN" `
  --category-map migration\data_preparation\category-map.csv
```

Generated files must be checked through Import Lite dry-run before apply.

Private prepared imports are operational artifacts and should not be committed.
