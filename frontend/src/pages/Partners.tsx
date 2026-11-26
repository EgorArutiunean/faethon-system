import { useEffect, useRef, useState } from "react";
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

type PartnerSort = "name" | "code" | "partner_type" | "created_at" | "is_active";
const PAGE_SIZE = 25;

export function Partners() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [rows, setRows] = useState<PartnerRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<PartnerSort>("name");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [partnerType, setPartnerType] = useState<Partner["partner_type"]>("customer");
  const [typeFilter, setTypeFilter] = useState("");
  const [phone, setPhone] = useState("");
  const [taxId, setTaxId] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [error, setError] = useState("");
  const loadRequest = useRef(0);

  function load() {
    const requestId = ++loadRequest.current;
    api.partnerPage({
      offset: page * PAGE_SIZE,
      limit: PAGE_SIZE,
      search,
      partner_type: typeFilter,
      sort_by: sortBy,
      sort_order: sortOrder
    })
      .then(async (result) => {
        if (requestId !== loadRequest.current) return;
        if (result.total > 0 && page * PAGE_SIZE >= result.total) {
          setPage(Math.max(0, Math.ceil(result.total / PAGE_SIZE) - 1));
          return;
        }
        const partners = result.items;
        const balances = await api.partnerBalances(partners.map((partner) => partner.id));
        if (requestId !== loadRequest.current) return;
        const byPartner = new Map<number, PartnerBalance>(balances.map((balance) => [balance.partner_id, balance]));
        setRows(partners.map((partner) => ({ ...partner, balance: byPartner.get(partner.id)?.balance ?? "0" })));
        setTotal(result.total);
        setError("");
      })
      .catch((exc) => {
        if (requestId !== loadRequest.current) return;
        setRows([]);
        setError(exc instanceof Error ? exc.message : t("apiLoadPartnersError"));
      });
  }

  function resetForm() {
    setEditorOpen(false);
    setCode("");
    setName("");
    setPhone("");
    setTaxId("");
    setPartnerType("customer");
    setEditingId(null);
  }

  function save() {
    if (!name.trim()) {
      setError(t("nameRequired"));
      return;
    }
    const payload = { code: code.trim() || null, name: name.trim(), partner_type: partnerType, phone: phone.trim() || null, tax_id: taxId.trim() || null, is_active: true };
    const request = editingId ? api.updatePartner(editingId, payload) : api.createPartner(payload);
    request.then(() => {
      resetForm();
      setError("");
      setRefreshVersion((current) => current + 1);
    }).catch((exc) => setError(exc instanceof Error ? exc.message : t("apiCreatePartnerError")));
  }

  function edit(row: Partner) {
    setEditorOpen(true);
    setEditingId(row.id);
    setCode(row.code ?? "");
    setName(row.name);
    setPartnerType(row.partner_type);
    setPhone(row.phone ?? "");
    setTaxId(row.tax_id ?? "");
  }

  function remove(row: Partner) {
    if (!window.confirm(t("deleteConfirm"))) return;
    api.deletePartner(row.id).then(() => setRefreshVersion((current) => current + 1)).catch((exc) => setError(exc instanceof Error ? exc.message : t("deleteError")));
  }

  useEffect(() => {
    const timeout = window.setTimeout(load, 250);
    return () => window.clearTimeout(timeout);
  }, [page, refreshVersion, search, sortBy, sortOrder, typeFilter]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <PageScaffold title={t("partners")}>
      <div className="workspace-command-bar"><button className="button primary" disabled={!can("partners.create")} onClick={() => { resetForm(); setEditorOpen(true); }} aria-expanded={editorOpen}>{t("create")}</button><span>{t("total")}: {total}</span></div>
      {editorOpen ? (
      <div className="panel form-grid" style={{ marginBottom: 10 }}>
        <div className="field"><label htmlFor="partner-code">{t("code")}</label><input id="partner-code" value={code} onChange={(event) => setCode(event.target.value)} /></div>
        <div className="field"><label htmlFor="partner-name">{t("name")}</label><input id="partner-name" value={name} onChange={(event) => setName(event.target.value)} /></div>
        <div className="field">
          <label htmlFor="partner-type">{t("partnerType")}</label>
          <select id="partner-type" value={partnerType} onChange={(event) => setPartnerType(event.target.value as Partner["partner_type"])}>
            <option value="customer">{t("customer")}</option>
            <option value="supplier">{t("supplier")}</option>
            <option value="both">{t("both")}</option>
          </select>
        </div>
        <div className="field"><label htmlFor="partner-phone">{t("phone")}</label><input id="partner-phone" value={phone} onChange={(event) => setPhone(event.target.value)} /></div>
        <div className="field"><label htmlFor="partner-tax-id">{t("taxId")}</label><input id="partner-tax-id" value={taxId} onChange={(event) => setTaxId(event.target.value)} /></div>
        <div className="field"><label>&nbsp;</label><button className="button primary" title={!can(editingId ? "partners.update" : "partners.create") ? t("noPermission") : ""} disabled={!can(editingId ? "partners.update" : "partners.create")} onClick={save}>{editingId ? t("save") : t("create")}</button></div>
        <div className="field"><label>&nbsp;</label><button className="button" onClick={resetForm}>{t("cancel")}</button></div>
      </div>
      ) : null}
      {error ? <div className="panel error-panel">{error}</div> : null}
      <div className="panel toolbar" style={{ padding: "8px 10px", marginBottom: 10 }}>
        <input className="search" aria-label={t("search")} value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder={t("search")} />
        <select aria-label={`${t("filter")}: ${t("partnerType")}`} value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value); setPage(0); }}>
          <option value="">{t("all")}: {t("partnerType")}</option>
          <option value="customer">{t("customer")}</option>
          <option value="supplier">{t("supplier")}</option>
          <option value="both">{t("both")}</option>
        </select>
        <select value={sortBy} onChange={(event) => { setSortBy(event.target.value as PartnerSort); setPage(0); }}>
          <option value="name">{t("name")}</option>
          <option value="code">{t("code")}</option>
          <option value="partner_type">{t("partnerType")}</option>
          <option value="created_at">ID</option>
          <option value="is_active">{t("active")}</option>
        </select>
        <button className="button" onClick={() => { setSortOrder((current) => current === "asc" ? "desc" : "asc"); setPage(0); }}>{sortOrder === "asc" ? "↑" : "↓"}</button>
        {search || typeFilter || sortBy !== "name" || sortOrder !== "asc" ? <button className="button" onClick={() => { setSearch(""); setTypeFilter(""); setSortBy("name"); setSortOrder("asc"); setPage(0); }}>{t("resetFilters")}</button> : null}
      </div>
      <DataTable<PartnerRow>
        rows={rows}
        emptyMessage={t("noPartners")}
        pageSize={PAGE_SIZE}
        columns={[
          { key: "code", header: t("code") },
          { key: "name", header: t("name") },
          { key: "partner_type", header: t("partnerType"), render: (row) => formatCode(row.partner_type, t) },
          { key: "phone", header: t("phone") },
          { key: "balance", header: t("balance"), render: (row) => formatMoney(row.balance) },
          { key: "statement", header: t("partnerStatement"), render: (row) => <Link to={`/partners/${row.id}/statement`}>{t("open")}</Link> },
          { key: "is_active", header: t("active"), render: (row) => row.is_active ? t("yes") : t("no") },
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
      {pageCount > 1 ? (
        <div className="panel table-footer">
          <span>{page + 1} / {pageCount} · {t("total")}: {total}</span>
          <span>
            <button className="button" disabled={page === 0} onClick={() => setPage((current) => Math.max(0, current - 1))}>‹</button>
            <button className="button" disabled={page >= pageCount - 1} onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))}>›</button>
          </span>
        </div>
      ) : null}
    </PageScaffold>
  );
}
