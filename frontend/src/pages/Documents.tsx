import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Document, Partner, Warehouse, api } from "../lib/api";

type DraftDocumentType = "incoming" | "outgoing" | "adjustment" | "transfer";
type DocumentSort = "id" | "number" | "document_date" | "status" | "document_type" | "total_amount" | "created_at";

const today = new Date().toISOString().slice(0, 10);
const PAGE_SIZE = 25;

function isDraftDocumentType(value: string | null): value is DraftDocumentType {
  return value === "incoming" || value === "outgoing" || value === "adjustment" || value === "transfer";
}

export function Documents() {
  const { t } = useI18n();
  const { showToast } = useToast();
  const { can } = useAuth();
  const [rows, setRows] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sortBy, setSortBy] = useState<DocumentSort>("document_date");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [partnerSearch, setPartnerSearch] = useState("");
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [error, setError] = useState("");
  const [searchParams] = useSearchParams();
  const requestedType = searchParams.get("create");
  const [draftForm, setDraftForm] = useState({
    document_type: isDraftDocumentType(requestedType) ? requestedType : "incoming" as DraftDocumentType,
    number: "",
    document_date: today,
    warehouse_id: "",
    destination_warehouse_id: "",
    partner_id: ""
  });
  const navigate = useNavigate();

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
        showToast("success", t("created"));
        navigate(`/documents/${doc.id}`);
      })
      .catch((exc) => {
        const message = exc instanceof Error ? exc.message : t("apiCreateDocumentError");
        setError(message);
        showToast("error", message);
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

  function deleteDraft(documentId: number) {
    if (!window.confirm(t("deleteDraftConfirm"))) return;
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

  function cancelPosted(documentId: number) {
    if (!window.confirm(t("cancelConfirm"))) return;
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
        .then((items) => active && setPartners(items))
        .catch((exc) => active && setError(exc instanceof Error ? exc.message : t("apiLoadPartnersError")));
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [draftForm.document_type, partnerSearch, t]);

  useEffect(() => {
    let active = true;
    const timeout = window.setTimeout(() => {
      api.documentPage({
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        search,
        document_type: typeFilter,
        status: statusFilter,
        sort_by: sortBy,
        sort_order: sortOrder
      }).then((result) => {
        if (!active) return;
        if (result.total > 0 && page * PAGE_SIZE >= result.total) {
          setPage(Math.max(0, Math.ceil(result.total / PAGE_SIZE) - 1));
          return;
        }
        setRows(result.items);
        setTotal(result.total);
        setError("");
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
  }, [page, refreshVersion, search, sortBy, sortOrder, statusFilter, t, typeFilter]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <PageScaffold title={t("documents")}>
      <div className="panel form-grid" style={{ marginBottom: 10 }}>
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
          <input value={draftForm.number} onChange={(event) => setDraftForm({ ...draftForm, number: event.target.value })} />
        </div>
        <div className="field">
          <label>{t("date")}</label>
          <input type="date" value={draftForm.document_date} onChange={(event) => setDraftForm({ ...draftForm, document_date: event.target.value })} />
        </div>
        <div className="field">
          <label>{t("status")}</label>
          <input value={t("draft")} readOnly />
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
            <div className="field"><label>{t("search")}: {t("partner")}</label><input value={partnerSearch} onChange={(event) => setPartnerSearch(event.target.value)} /></div>
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
      <div className="toolbar">
        <button data-testid="draft-document-create" className="button primary" title={!can("documents.create") ? t("noPermission") : ""} disabled={!can("documents.create")} onClick={createDraft}>{t("createDocument")}</button>
      </div>
      {error ? <div className="panel error-panel">{error}</div> : null}
      <div className="panel toolbar" style={{ padding: "8px 10px", marginBottom: 10 }}>
        <input className="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder={t("search")} />
        <select value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value); setPage(0); }}>
          <option value="">{t("all")}: {t("type")}</option>
          <option value="incoming">{t("incoming")}</option>
          <option value="outgoing">{t("outgoing")}</option>
          <option value="adjustment">{t("adjustment")}</option>
          <option value="transfer">{t("transfer")}</option>
        </select>
        <select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(0); }}>
          <option value="">{t("all")}: {t("status")}</option>
          <option value="draft">{t("draft")}</option>
          <option value="posted">{t("posted")}</option>
          <option value="cancelled">{t("cancelled")}</option>
        </select>
        <select value={sortBy} onChange={(event) => { setSortBy(event.target.value as DocumentSort); setPage(0); }}>
          <option value="document_date">{t("date")}</option>
          <option value="id">ID</option>
          <option value="number">{t("number")}</option>
          <option value="total_amount">{t("total")}</option>
          <option value="status">{t("status")}</option>
        </select>
        <button className="button" onClick={() => { setSortOrder((current) => current === "asc" ? "desc" : "asc"); setPage(0); }}>{sortOrder === "asc" ? "↑" : "↓"}</button>
      </div>
      <DataTable<Document>
        rows={rows}
        emptyMessage={t("noDocuments")}
        pageSize={PAGE_SIZE}
        columns={[
          { key: "id", header: "ID", render: (row) => <Link to={`/documents/${row.id}`}>{row.id}</Link> },
          { key: "document_type", header: t("type"), render: (row) => formatCode(row.document_type, t) },
          { key: "number", header: t("number") },
          { key: "document_date", header: t("date"), render: (row) => formatDate(row.document_date) },
          { key: "status", header: t("status"), render: (row) => <StatusBadge status={row.status} label={formatCode(row.status, t)} /> },
          { key: "partner_name", header: t("partner") },
          { key: "warehouse_name", header: t("warehouse") },
          { key: "destination_warehouse_name", header: t("destinationWarehouse") },
          { key: "total_amount", header: t("total"), render: (row) => formatMoney(row.total_amount) },
          {
            key: "actions",
            header: t("actions"),
            render: (row) => (
              <div style={{ display: "flex", gap: 6 }}>
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
