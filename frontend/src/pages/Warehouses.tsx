import { useEffect, useState } from "react";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { Warehouse, api } from "../lib/api";

export function Warehouses() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [rows, setRows] = useState<Warehouse[]>([]);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [error, setError] = useState("");

  function load() {
    api.warehouses().then(setRows).catch((exc) => {
      setRows([]);
      setError(exc instanceof Error ? exc.message : t("apiLoadWarehousesError"));
    });
  }

  function resetForm() {
    setEditorOpen(false);
    setCode("");
    setName("");
    setAddress("");
    setEditingId(null);
  }

  function save() {
    if (!name.trim()) {
      setError(t("nameRequired"));
      return;
    }
    const payload = { code: code.trim() || null, name: name.trim(), address: address.trim() || null };
    const request = editingId ? api.updateWarehouse(editingId, payload) : api.createWarehouse(payload);
    request.then(() => {
      resetForm();
      setError("");
      load();
    }).catch((exc) => setError(exc instanceof Error ? exc.message : t("apiCreateWarehouseError")));
  }

  function edit(row: Warehouse) {
    setEditorOpen(true);
    setEditingId(row.id);
    setCode(row.code ?? "");
    setName(row.name);
    setAddress(row.address ?? "");
  }

  function remove(row: Warehouse) {
    if (!window.confirm(t("deleteConfirm"))) return;
    api.deleteWarehouse(row.id).then(load).catch((exc) => setError(exc instanceof Error ? exc.message : t("deleteError")));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <PageScaffold title={t("warehouses")}>
      <div className="workspace-command-bar"><button className="button primary" disabled={!can("warehouses.create")} onClick={() => { resetForm(); setEditorOpen(true); }} aria-expanded={editorOpen}>{t("create")}</button><span>{t("total")}: {rows.length}</span></div>
      {editorOpen ? (
      <div className="panel form-grid" style={{ marginBottom: 10 }}>
        <div className="field"><label htmlFor="warehouse-code">{t("code")}</label><input id="warehouse-code" value={code} onChange={(event) => setCode(event.target.value)} /></div>
        <div className="field"><label htmlFor="warehouse-name">{t("name")}</label><input id="warehouse-name" value={name} onChange={(event) => setName(event.target.value)} /></div>
        <div className="field"><label htmlFor="warehouse-address">{t("address")}</label><input id="warehouse-address" value={address} onChange={(event) => setAddress(event.target.value)} /></div>
        <div className="field"><label>&nbsp;</label><button className="button primary" title={!can(editingId ? "warehouses.update" : "warehouses.create") ? t("noPermission") : ""} disabled={!can(editingId ? "warehouses.update" : "warehouses.create")} onClick={save}>{editingId ? t("save") : t("create")}</button></div>
        <div className="field"><label>&nbsp;</label><button className="button" onClick={resetForm}>{t("cancel")}</button></div>
      </div>
      ) : null}
      {error ? <div className="panel error-panel">{error}</div> : null}
      <DataTable<Warehouse>
        rows={rows}
        emptyMessage={t("noWarehouses")}
        searchable
        columns={[
          { key: "code", header: t("code"), sortable: true },
          { key: "name", header: t("name"), sortable: true },
          { key: "address", header: t("address"), sortable: true },
          {
            key: "actions",
            header: t("actions"),
            render: (row) => (
              <div style={{ display: "flex", gap: 6 }}>
                <button className="button" title={!can("warehouses.update") ? t("noPermission") : ""} disabled={!can("warehouses.update")} onClick={() => edit(row)}>{t("edit")}</button>
                <button className="button" title={!can("warehouses.delete") ? t("noPermission") : ""} disabled={!can("warehouses.delete")} onClick={() => remove(row)}>{t("delete")}</button>
              </div>
            )
          }
        ]}
      />
    </PageScaffold>
  );
}
