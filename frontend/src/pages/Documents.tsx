import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { JournalViews } from "../components/JournalViews";
import { DraftRecoveryNotice } from "../components/DraftRecoveryNotice";
import { useConfirmDialog } from "../components/ConfirmDialog";
import { useAuth } from "../auth";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Document, Partner, Warehouse, api } from "../lib/api";
import { JournalConfig, useJournalState } from "../lib/journalState";
import { useLocalDraft } from "../hooks/useLocalDraft";

type DraftDocumentType = "incoming" | "outgoing" | "adjustment" | "transfer";
type DocumentSort = "id" | "number" | "document_date" | "status" | "document_type" | "total_amount" | "created_at";

const today = new Date().toISOString().slice(0, 10);
const PAGE_SIZE = 25;
const JOURNAL_CONFIG: JournalConfig<DocumentSort> = {
  id: "documents", defaultSort: "document_date",
  sorts: ["id", "number", "document_date", "status", "document_type", "total_amount", "created_at"],
  types: ["incoming", "outgoing", "adjustment", "transfer"],
};

function isDraftDocumentType(value: string | null): value is DraftDocumentType {
  return value === "incoming" || value === "outgoing" || value === "adjustment" || value === "transfer";
}

export function Documents() {
  const { t } = useI18n();
  const { showToast } = useToast();
  const { ask, dialog } = useConfirmDialog();
  const { can } = useAuth();
  const [searchParams] = useSearchParams();
  const [rows, setRows] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const journal = useJournalState(JOURNAL_CONFIG);
  const { page, search, dateFrom, typeFilter, statusFilter, sortBy, sortOrder } = journal.state;
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [partnerSearch, setPartnerSearch] = useState("");
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [error, setError] = useState("");
  const requestedType = searchParams.get("create");
  const createIdentity = isDraftDocumentType(requestedType) ? requestedType : "general";
  const currentCreateIdentity = useRef(createIdentity);
  currentCreateIdentity.current = createIdentity;
  const mounted = useRef(true);
  const creatingRef = useRef(false);
  const [creating, setCreating] = useState(false);
  const [preparedCreateIdentity, setPreparedCreateIdentity] = useState(createIdentity);
  const [draftOpen, setDraftOpen] = useState(isDraftDocumentType(requestedType));
  const [draftForm, setDraftForm] = useState({
    document_type: isDraftDocumentType(requestedType) ? requestedType : "incoming" as DraftDocumentType,
    number: "",
    document_date: today,
    warehouse_id: "",
    destination_warehouse_id: "",
    partner_id: ""
  });
  const navigate = useNavigate();
  const defaultWarehouseId = warehouses.length === 1 ? String(warehouses[0].id) : "";
  function resetCreateForm(open: boolean) {
    setDraftForm({ document_type: isDraftDocumentType(requestedType) ? requestedType : "incoming", number: "", document_date: today, warehouse_id: defaultWarehouseId, destination_warehouse_id: "", partner_id: "" });
    setPartnerSearch("");
    setDraftOpen(open);
    setError("");
  }
  type CreateInput = { form: typeof draftForm; partnerSearch: string };
  const draft = useLocalDraft<CreateInput>({
    scope: "document-create", entityId: createIdentity, revision: "new",
    value: { form: draftForm, partnerSearch },
    dirty: draftOpen && (draftForm.number.trim() !== "" || draftForm.document_date !== today || draftForm.warehouse_id !== defaultWarehouseId
      || draftForm.destination_warehouse_id !== "" || draftForm.partner_id !== "" || partnerSearch !== ""
      || draftForm.document_type !== (isDraftDocumentType(requestedType) ? requestedType : "incoming")),
    enabled: can("documents.create") && preparedCreateIdentity === createIdentity,
    validate: (value) => {
      if (!value || typeof value !== "object") return false;
      const saved = value as CreateInput;
      return typeof saved.partnerSearch === "string" && Boolean(saved.form)
        && Object.keys(draftForm).every((key) => typeof saved.form[key as keyof typeof draftForm] === "string")
        && isDraftDocumentType(saved.form.document_type);
    },
    onRestore: (saved) => {
      setDraftForm(saved.form);
      setPartnerSearch(saved.partnerSearch);
      setDraftOpen(true);
      if (saved.form.partner_id) api.partner(Number(saved.form.partner_id)).then((partner) => {
        setPartners((current) => current.some((item) => item.id === partner.id) ? current : [partner, ...current]);
      }).catch(() => undefined);
    },
    onDiscard: () => resetCreateForm(true),
  });

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    if (preparedCreateIdentity === createIdentity) return;
    resetCreateForm(isDraftDocumentType(requestedType));
    setPreparedCreateIdentity(createIdentity);
  }, [createIdentity, preparedCreateIdentity]);

  const partnersForType = useMemo(() => {
    if (draftForm.document_type === "incoming") {
      return partners.filter((partner) => partner.partner_type === "supplier" || partner.partner_type === "both");
    }
    if (draftForm.document_type === "outgoing") {
      return partners.filter((partner) => partner.partner_type === "customer" || partner.partner_type === "both");
    }
    return [];
  }, [draftForm.document_type, partners]);

  function setDocumentType(documentType: DraftDocumentType) {
    setDraftForm((current) => ({
      ...current,
      document_type: documentType,
      partner_id: "",
      destination_warehouse_id: documentType === "transfer" ? current.destination_warehouse_id : ""
    }));
  }

  function failValidation(message: string) {
    setError(message);
    showToast("error", message);
  }

  function createDraft() {
    if (creatingRef.current || !can("documents.create")) return;
    setError("");
    if (!draftForm.warehouse_id) {
      failValidation(t("selectWarehouse"));
      return;
    }
    if ((draftForm.document_type === "incoming" || draftForm.document_type === "outgoing") && !draftForm.partner_id) {
      failValidation(t("selectPartner"));
      return;
    }
    if (draftForm.document_type === "transfer") {
      if (!draftForm.destination_warehouse_id) {
        failValidation(t("selectDestinationWarehouse"));
        return;
      }
      if (draftForm.destination_warehouse_id === draftForm.warehouse_id) {
        failValidation(t("differentWarehousesRequired"));
        return;
      }
    }

    creatingRef.current = true;
    setCreating(true);
    const submittedIdentity = createIdentity;
    api
      .createDocument({
        document_type: draftForm.document_type,
        number: draftForm.number.trim() || null,
        document_date: draftForm.document_date,
        status: "draft",
        partner_id: draftForm.partner_id ? Number(draftForm.partner_id) : null,
        warehouse_id: Number(draftForm.warehouse_id),
        destination_warehouse_id: draftForm.destination_warehouse_id ? Number(draftForm.destination_warehouse_id) : null,
        total_amount: "0"
      })
      .then((doc) => {
        draft.clear();
        showToast("success", t("created"));
        if (mounted.current && currentCreateIdentity.current === submittedIdentity) navigate(`/documents/${doc.id}`);
      })
      .catch((exc) => {
        const message = exc instanceof Error ? exc.message : t("apiCreateDocumentError");
        setError(message);
        showToast("error", message);
      })
      .finally(() => {
        creatingRef.current = false;
        if (mounted.current) setCreating(false);
      });
  }

  function printDocument(documentId: number) {
    setError("");
    api.printDocument(documentId)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank", "noopener,noreferrer");
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
        showToast("success", t("printOpened"));
      })
      .catch((exc) => {
        const message = exc instanceof Error ? exc.message : t("printError");
        setError(message);
        showToast("error", message);
      });
  }

  function loadDirectories() {
    api.warehouses().then((warehouseRows) => {
      setWarehouses(warehouseRows);
      if (warehouseRows.length === 1) {
        setDraftForm((current) => ({
          ...current,
          warehouse_id: current.warehouse_id || String(warehouseRows[0].id)
        }));
      }
    }).catch((exc) => {
      const message = exc instanceof Error ? exc.message : t("apiLoadWarehousesError");
      setError(message);
    });
  }

  function refreshRegistry() {
    setRefreshVersion((current) => current + 1);
  }

  async function deleteDraft(documentId: number) {
    if (!(await ask({ message: `${t("deleteDraftConfirm")} #${documentId}`, confirmLabel: t("deleteDraft"), danger: true }))) return;
    api.deleteDocument(documentId)
      .then(() => {
        showToast("success", t("deleteDraft"));
        refreshRegistry();
      })
      .catch((exc) => {
        const message = exc instanceof Error ? exc.message : String(exc);
        setError(message);
        showToast("error", message);
      });
  }

  async function cancelPosted(documentId: number) {
    if (!(await ask({ message: `${t("cancelConfirm")} #${documentId}`, confirmLabel: t("cancel"), danger: true }))) return;
    api.cancelDocument(documentId)
      .then(() => {
        showToast("success", t("cancelledSuccess"));
        refreshRegistry();
      })
      .catch((exc) => {
        const message = exc instanceof Error ? exc.message : String(exc);
        setError(message);
        showToast("error", message);
      });
  }

  useEffect(() => {
    loadDirectories();
  }, []);

  useEffect(() => {
    if (draftForm.document_type === "transfer" || draftForm.document_type === "adjustment") {
      setPartners([]);
      return;
    }
    let active = true;
    const timeout = window.setTimeout(() => {
      api.partnerOptions(partnerSearch, draftForm.document_type === "incoming" ? "supplier" : "customer")
        .then((items) => active && setPartners((current) => {
          const selected = current.find((partner) => String(partner.id) === draftForm.partner_id);
          return selected && !items.some((partner) => partner.id === selected.id) ? [selected, ...items] : items;
        }))
        .catch((exc) => active && setError(exc instanceof Error ? exc.message : t("apiLoadPartnersError")));
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [draftForm.document_type, draftForm.partner_id, partnerSearch, t]);

  useEffect(() => {
    let active = true;
    const timeout = window.setTimeout(() => {
      api.documentPage({
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        search,
        date_from: dateFrom,
        document_type: typeFilter,
        status: statusFilter,
        sort_by: sortBy,
        sort_order: sortOrder
      }).then((result) => {
        if (!active) return;
        if (page > 0 && page * PAGE_SIZE >= result.total) {
          journal.update({ page: Math.max(0, Math.ceil(result.total / PAGE_SIZE) - 1) });
          return;
        }
        setRows(result.items);
        setTotal(result.total);
        setError("");
        journal.markLoaded();
      }).catch((exc) => {
        if (!active) return;
        setRows([]);
        setTotal(0);
        setError(exc instanceof Error ? exc.message : t("apiLoadDocumentsError"));
      });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [dateFrom, page, refreshVersion, search, sortBy, sortOrder, statusFilter, t, typeFilter]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="document-registry">
      {dialog}
      <div className="document-registry-heading">
        <div><h1>{t("documents")}</h1><Link to="/document-history">История накладных из старой базы</Link><br /><span>{t("documentRegistryHint")}</span></div>
        <button className="button primary" disabled={creating || !can("documents.create")} onClick={() => { if (draftOpen) { draft.clear(); resetCreateForm(false); } else setDraftOpen(true); }} aria-expanded={draftOpen} aria-controls="document-draft-form">{draftOpen ? t("close") : t("createDocument")}</button>
      </div>
      {draftOpen ? <section className="panel document-draft-section" id="document-draft-form" aria-label={t("createDocument")}>
        <div className="document-section-title"><h2>{t("createDocument")}</h2></div>
        <fieldset disabled={creating} style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}>
        <DraftRecoveryNotice draft={draft} />
        <div className="document-draft-grid form-grid">
        <div className="field">
          <label>{t("type")}</label>
          <select data-testid="draft-document-type" value={draftForm.document_type} onChange={(event) => setDocumentType(event.target.value as DraftDocumentType)}>
            <option value="incoming">{t("incoming")}</option>
            <option value="outgoing">{t("outgoing")}</option>
            <option value="adjustment">{t("adjustment")}</option>
            <option value="transfer">{t("transfer")}</option>
          </select>
        </div>
        <div className="field">
          <label>{t("number")}</label>
          <input data-testid="draft-document-number" value={draftForm.number} onChange={(event) => setDraftForm({ ...draftForm, number: event.target.value })} />
        </div>
        <div className="field">
          <label>{t("date")}</label>
          <input data-testid="draft-document-date" type="date" value={draftForm.document_date} onChange={(event) => setDraftForm({ ...draftForm, document_date: event.target.value })} />
        </div>
        <div className="field">
          <label>{draftForm.document_type === "transfer" ? t("sourceWarehouse") : t("warehouse")}</label>
          <select data-testid="draft-document-warehouse" value={draftForm.warehouse_id} onChange={(event) => setDraftForm({ ...draftForm, warehouse_id: event.target.value })}>
            <option value="">{t("selectWarehouse")}</option>
            {warehouses.map((warehouse) => (
              <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>
            ))}
          </select>
        </div>
        {draftForm.document_type === "transfer" ? (
          <div className="field">
            <label>{t("destinationWarehouse")}</label>
            <select data-testid="draft-document-destination" value={draftForm.destination_warehouse_id} onChange={(event) => setDraftForm({ ...draftForm, destination_warehouse_id: event.target.value })}>
              <option value="">{t("selectDestinationWarehouse")}</option>
              {warehouses.map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>
              ))}
            </select>
          </div>
        ) : null}
        {draftForm.document_type === "incoming" || draftForm.document_type === "outgoing" ? (
          <>
            <div className="field"><label>{t("search")}: {t("partner")}</label><input data-testid="draft-document-partner-search" value={partnerSearch} onChange={(event) => setPartnerSearch(event.target.value)} /></div>
            <div className="field">
              <label>{draftForm.document_type === "incoming" ? t("supplier") : t("customer")}</label>
              <select data-testid="draft-document-partner" value={draftForm.partner_id} onChange={(event) => setDraftForm({ ...draftForm, partner_id: event.target.value })}>
                <option value="">{t("selectPartner")}</option>
                {partnersForType.map((partner) => (
                  <option key={partner.id} value={partner.id}>{partner.name}</option>
                ))}
              </select>
            </div>
          </>
        ) : null}
        </div>
        <div className="document-draft-actions"><button data-testid="draft-document-create" className="button primary" title={!can("documents.create") ? t("noPermission") : ""} disabled={creating || !can("documents.create")} onClick={createDraft}>{creating ? t("loading") : t("createDocument")}</button></div>
        </fieldset>
      </section> : null}
      {error ? <div className="panel error-panel">{error}</div> : null}
      <section className="document-registry-panel panel" aria-label={t("documentRegistry")}>
      <div className="document-registry-title"><h2>{t("documentRegistry")}</h2><span>{total}</span></div>
      <JournalViews {...journal} />
      <div className="document-registry-filters">
        <input className="search" aria-label={t("search")} value={search} onChange={(event) => journal.update({ search: event.target.value, page: 0 })} placeholder={t("search")} />
        <label className="journal-date-filter">С даты <input type="date" value={dateFrom} onChange={(event) => journal.update({ dateFrom: event.target.value, page: 0 })} /></label>
        <select aria-label={`${t("filter")}: ${t("type")}`} value={typeFilter} onChange={(event) => journal.update({ typeFilter: event.target.value, page: 0 })}>
          <option value="">{t("all")}: {t("type")}</option>
          <option value="incoming">{t("incoming")}</option>
          <option value="outgoing">{t("outgoing")}</option>
          <option value="adjustment">{t("adjustment")}</option>
          <option value="transfer">{t("transfer")}</option>
        </select>
        <select aria-label={`${t("filter")}: ${t("status")}`} value={statusFilter} onChange={(event) => journal.update({ statusFilter: event.target.value, page: 0 })}>
          <option value="">{t("all")}: {t("status")}</option>
          <option value="draft">{t("draft")}</option>
          <option value="posted">{t("posted")}</option>
          <option value="cancelled">{t("cancelled")}</option>
        </select>
        <select aria-label={t("sortBy")} value={sortBy} onChange={(event) => journal.update({ sortBy: event.target.value as DocumentSort, page: 0 })}>
          <option value="document_date">{t("date")}</option>
          <option value="id">ID</option>
          <option value="number">{t("number")}</option>
          <option value="total_amount">{t("total")}</option>
          <option value="status">{t("status")}</option>
        </select>
        <button className="button" aria-label={t("sortDirection")} onClick={() => journal.update({ sortOrder: sortOrder === "asc" ? "desc" : "asc", page: 0 })}>{sortOrder === "asc" ? "↑" : "↓"}</button>
        {search || dateFrom || typeFilter || statusFilter || sortBy !== "document_date" || sortOrder !== "desc" ? <button className="button" onClick={journal.reset}>{t("resetFilters")}</button> : null}
      </div>
      <DataTable<Document>
        rows={rows}
        emptyMessage={t("noDocuments")}
        pageSize={PAGE_SIZE}
        columns={[
          { key: "document_type", header: t("type"), render: (row) => formatCode(row.document_type, t) },
          { key: "number", header: t("number"), render: (row) => <Link to={`/documents/${row.id}`}>{row.number || `#${row.id}`}</Link> },
          { key: "document_date", header: t("date"), render: (row) => formatDate(row.document_date) },
          { key: "status", header: t("status"), render: (row) => <StatusBadge status={row.status} label={formatCode(row.status, t)} /> },
          { key: "partner_name", header: t("partner") },
          { key: "warehouse_name", header: t("warehouse"), render: (row) => row.destination_warehouse_name ? `${row.warehouse_name ?? ""} → ${row.destination_warehouse_name}` : row.warehouse_name ?? "" },
          { key: "total_amount", header: t("total"), render: (row) => formatMoney(row.total_amount) },
          {
            key: "actions",
            header: t("actions"),
            render: (row) => (
              <div className="document-row-actions">
                <Link className="button" to={`/documents/${row.id}`}>{t("open")}</Link>
                <button className="button" title={!can("documents.read") ? t("noPermission") : ""} disabled={!can("documents.read")} onClick={() => printDocument(row.id)}>{t("print")}</button>
                {row.status === "draft" ? (
                  <button className="button" title={!can("documents.delete") ? t("noPermission") : ""} disabled={!can("documents.delete")} onClick={() => deleteDraft(row.id)}>{t("deleteDraft")}</button>
                ) : null}
                {row.status === "posted" ? (
                  <button className="button" title={!can("documents.cancel") ? t("noPermission") : ""} disabled={!can("documents.cancel")} onClick={() => cancelPosted(row.id)}>{t("cancel")}</button>
                ) : null}
              </div>
            )
          }
        ]}
      />
      {pageCount > 1 ? (
        <div className="table-footer">
          <span>{page + 1} / {pageCount} · {t("total")}: {total}</span>
          <span>
            <button className="button" disabled={page === 0} onClick={() => journal.update({ page: Math.max(0, page - 1) })}>‹</button>
            <button className="button" disabled={page >= pageCount - 1} onClick={() => journal.update({ page: Math.min(pageCount - 1, page + 1) })}>›</button>
          </span>
        </div>
      ) : null}
      </section>
    </div>
  );
}
