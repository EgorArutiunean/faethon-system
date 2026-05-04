import { useEffect, useState } from "react";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { formatMoney } from "../format";
import { useI18n } from "../i18n";
import { Product, api } from "../lib/api";

export function Products() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [rows, setRows] = useState<Product[]>([]);
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [basePrice, setBasePrice] = useState("0");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  function load() {
    api.products().then(setRows).catch((exc) => {
      setRows([]);
      setError(exc instanceof Error ? exc.message : t("apiLoadProductsError"));
    });
  }

  function resetForm() {
    setSku("");
    setName("");
    setBasePrice("0");
    setEditingId(null);
  }

  function save() {
    if (!name) return;
    const payload = { sku: sku || null, name, base_price: basePrice, is_active: true };
    const request = editingId ? api.updateProduct(editingId, payload) : api.createProduct(payload);
    request.then(() => {
      resetForm();
      setError("");
      load();
    }).catch((exc) => setError(exc instanceof Error ? exc.message : t("apiCreateProductError")));
  }

  function edit(row: Product) {
    setEditingId(row.id);
    setSku(row.sku ?? "");
    setName(row.name);
    setBasePrice(String(row.base_price ?? "0"));
  }

  function remove(row: Product) {
    if (!window.confirm(t("deleteConfirm"))) return;
    api.deleteProduct(row.id).then(load).catch((exc) => setError(exc instanceof Error ? exc.message : t("deleteError")));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <PageScaffold title={t("products")}>
      <div className="panel form-grid" style={{ marginBottom: 10 }}>
        <div className="field"><label>SKU</label><input value={sku} onChange={(event) => setSku(event.target.value)} /></div>
        <div className="field"><label>{t("name")}</label><input value={name} onChange={(event) => setName(event.target.value)} /></div>
        <div className="field"><label>{t("basePrice")}</label><input value={basePrice} onChange={(event) => setBasePrice(event.target.value)} /></div>
        <div className="field"><label>{t("status")}</label><select><option>{t("active")}</option></select></div>
        <div className="field"><label>&nbsp;</label><button className="button primary" title={!can(editingId ? "products.update" : "products.create") ? t("noPermission") : ""} disabled={!can(editingId ? "products.update" : "products.create")} onClick={save}>{editingId ? t("save") : t("create")}</button></div>
        {editingId ? <div className="field"><label>&nbsp;</label><button className="button" onClick={resetForm}>{t("cancel")}</button></div> : null}
      </div>
      {error ? <div className="panel error-panel">{error}</div> : null}
      <DataTable<Product>
        rows={rows}
        emptyMessage={t("noProducts")}
        searchable
        columns={[
          { key: "sku", header: "SKU", sortable: true },
          { key: "name", header: t("name"), sortable: true },
          { key: "base_price", header: t("basePrice"), sortable: true, render: (row) => formatMoney(row.base_price) },
          { key: "is_active", header: t("active"), sortable: true },
          {
            key: "actions",
            header: t("actions"),
            render: (row) => (
              <div style={{ display: "flex", gap: 6 }}>
                <button className="button" title={!can("products.update") ? t("noPermission") : ""} disabled={!can("products.update")} onClick={() => edit(row)}>{t("edit")}</button>
                <button className="button" title={!can("products.delete") ? t("noPermission") : ""} disabled={!can("products.delete")} onClick={() => remove(row)}>{t("delete")}</button>
              </div>
            )
          }
        ]}
      />
    </PageScaffold>
  );
}
