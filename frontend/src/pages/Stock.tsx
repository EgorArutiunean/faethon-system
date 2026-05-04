import { useEffect, useState } from "react";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useI18n } from "../i18n";
import { StockBalance, StockMovement, Warehouse, api } from "../lib/api";

export function Stock() {
  const { t } = useI18n();
  const [rows, setRows] = useState<StockBalance[]>([]);
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [warehouseId, setWarehouseId] = useState("");
  const [productSearch, setProductSearch] = useState("");
  const [tab, setTab] = useState<"balances" | "movements">("balances");
  const [error, setError] = useState("");

  useEffect(() => {
    api.warehouses().then(setWarehouses).catch((exc) => {
      setWarehouses([]);
      setError(exc instanceof Error ? exc.message : t("apiLoadWarehousesError"));
    });
  }, []);

  useEffect(() => {
    const params = warehouseId ? `?warehouse_id=${warehouseId}` : "";
    api.stockBalances(params).then(setRows).catch((exc) => {
      setRows([]);
      setError(exc instanceof Error ? exc.message : t("apiLoadStockBalancesError"));
    });
    api.stockMovements(params).then(setMovements).catch((exc) => {
      setMovements([]);
      setError(exc instanceof Error ? exc.message : t("apiLoadStockMovementsError"));
    });
  }, [warehouseId]);

  const normalizedSearch = productSearch.toLowerCase();
  const filteredRows = rows.filter((row) =>
    `${row.product_id} ${row.product_name ?? ""}`.toLowerCase().includes(normalizedSearch)
  );
  const filteredMovements = movements.filter((row) =>
    `${row.product_id} ${row.product_name ?? ""} ${row.document_number ?? ""}`.toLowerCase().includes(normalizedSearch)
  );

  return (
    <PageScaffold title={t("stock")}>
      <div className="toolbar">
        <button className={`button ${tab === "balances" ? "primary" : ""}`} onClick={() => setTab("balances")}>{t("balances")}</button>
        <button className={`button ${tab === "movements" ? "primary" : ""}`} onClick={() => setTab("movements")}>{t("movements")}</button>
      </div>
      <div className="panel form-grid" style={{ marginBottom: 10 }}>
        <div className="field">
          <label>{t("warehouse")}</label>
          <select value={warehouseId} onChange={(event) => setWarehouseId(event.target.value)}>
            <option value="">{t("allWarehouses")}</option>
            {warehouses.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label>{t("productSearch")}</label>
          <input value={productSearch} onChange={(event) => setProductSearch(event.target.value)} />
        </div>
      </div>
      {error ? <div className="panel error-panel">{error}</div> : null}
      {tab === "balances" ? (
        <DataTable
          rows={filteredRows}
          emptyMessage={t("noStockBalances")}
          columns={[
            { key: "warehouse_name", header: t("warehouse") },
            { key: "product_name", header: t("product") },
            { key: "quantity", header: t("quantity") }
          ]}
        />
      ) : (
        <DataTable
          rows={filteredMovements}
          emptyMessage={t("noStockMovements")}
          columns={[
            { key: "created_at", header: t("date") },
            { key: "product_name", header: t("product") },
            { key: "warehouse_name", header: t("warehouse") },
            { key: "document_number", header: t("document") },
            { key: "movement_type", header: t("movement") },
            { key: "quantity_delta", header: t("quantity") },
            { key: "document_id", header: t("sourceId") }
          ]}
        />
      )}
      <p style={{ color: "#52616f", fontSize: 13 }}>
        TODO LEGACY_RULE_REQUIRED: balance source of truth and recalculation rules.
      </p>
    </PageScaffold>
  );
}
