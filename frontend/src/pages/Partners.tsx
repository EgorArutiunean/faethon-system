import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { formatCode, formatMoney } from "../format";
import { useI18n } from "../i18n";
import { Partner, PartnerBalance, api } from "../lib/api";

type PartnerRow = Partner & {
  balance?: string;
};

export function Partners() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [rows, setRows] = useState<PartnerRow[]>([]);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [partnerType, setPartnerType] = useState<Partner["partner_type"]>("customer");
  const [typeFilter, setTypeFilter] = useState("");
  const [phone, setPhone] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  function load() {
    const query = typeFilter ? `?partner_type=${typeFilter}` : "";
    Promise.all([api.partners(query), api.partnerBalances()])
      .then(([partners, balances]) => {
        const byPartner = new Map<number, PartnerBalance>(balances.map((balance) => [balance.partner_id, balance]));
        setRows(partners.map((partner) => ({ ...partner, balance: byPartner.get(partner.id)?.balance ?? "0" })));
      })
      .catch((exc) => {
        setRows([]);
        setError(exc instanceof Error ? exc.message : t("apiLoadPartnersError"));
      });
  }

  function resetForm() {
    setCode("");
    setName("");
    setPhone("");
    setPartnerType("customer");
    setEditingId(null);
  }

  function save() {
    if (!name) return;
    const payload = { code: code || null, name, partner_type: partnerType, phone: phone || null, is_active: true };
    const request = editingId ? api.updatePartner(editingId, payload) : api.createPartner(payload);
    request.then(() => {
      resetForm();
      setError("");
      load();
    }).catch((exc) => setError(exc instanceof Error ? exc.message : t("apiCreatePartnerError")));
  }

  function edit(row: Partner) {
    setEditingId(row.id);
    setCode(row.code ?? "");
    setName(row.name);
    setPartnerType(row.partner_type);
    setPhone(row.phone ?? "");
  }

  function remove(row: Partner) {
    if (!window.confirm(t("deleteConfirm"))) return;
    api.deletePartner(row.id).then(load).catch((exc) => setError(exc instanceof Error ? exc.message : t("deleteError")));
  }

  useEffect(() => {
    load();
  }, [typeFilter]);

  return (
    <PageScaffold title={t("partners")}>
      <div className="panel form-grid" style={{ marginBottom: 10 }}>
        <div className="field"><label>{t("code")}</label><input value={code} onChange={(event) => setCode(event.target.value)} /></div>
        <div className="field"><label>{t("name")}</label><input value={name} onChange={(event) => setName(event.target.value)} /></div>
        <div className="field">
          <label>{t("partnerType")}</label>
          <select value={partnerType} onChange={(event) => setPartnerType(event.target.value as Partner["partner_type"])}>
            <option value="customer">{t("customer")}</option>
            <option value="supplier">{t("supplier")}</option>
            <option value="both">{t("both")}</option>
          </select>
        </div>
        <div className="field"><label>{t("phone")}</label><input value={phone} onChange={(event) => setPhone(event.target.value)} /></div>
        <div className="field"><label>{t("taxId")}</label><input /></div>
        <div className="field"><label>&nbsp;</label><button className="button primary" title={!can(editingId ? "partners.update" : "partners.create") ? t("noPermission") : ""} disabled={!can(editingId ? "partners.update" : "partners.create")} onClick={save}>{editingId ? t("save") : t("create")}</button></div>
        {editingId ? <div className="field"><label>&nbsp;</label><button className="button" onClick={resetForm}>{t("cancel")}</button></div> : null}
        <div className="field">
          <label>{t("filter")}: {t("partnerType")}</label>
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
            <option value="">{t("all")}</option>
            <option value="customer">{t("customer")}</option>
            <option value="supplier">{t("supplier")}</option>
            <option value="both">{t("both")}</option>
          </select>
        </div>
      </div>
      {error ? <div className="panel error-panel">{error}</div> : null}
      <DataTable<PartnerRow>
        rows={rows}
        emptyMessage={t("noPartners")}
        searchable
        columns={[
          { key: "code", header: t("code"), sortable: true },
          { key: "name", header: t("name"), sortable: true },
          { key: "partner_type", header: t("partnerType"), sortable: true, render: (row) => formatCode(row.partner_type, t) },
          { key: "phone", header: t("phone"), sortable: true },
          { key: "balance", header: t("balance"), sortable: true, render: (row) => formatMoney(row.balance) },
          { key: "statement", header: t("partnerStatement"), render: (row) => <Link to={`/partners/${row.id}/statement`}>{t("open")}</Link> },
          { key: "is_active", header: t("active"), sortable: true, render: (row) => row.is_active ? t("yes") : t("no") },
          {
            key: "actions",
            header: t("actions"),
            render: (row) => (
              <div style={{ display: "flex", gap: 6 }}>
                <button className="button" title={!can("partners.update") ? t("noPermission") : ""} disabled={!can("partners.update")} onClick={() => edit(row)}>{t("edit")}</button>
                <button className="button" title={!can("partners.delete") ? t("noPermission") : ""} disabled={!can("partners.delete")} onClick={() => remove(row)}>{t("delete")}</button>
              </div>
            )
          }
        ]}
      />
    </PageScaffold>
  );
}
