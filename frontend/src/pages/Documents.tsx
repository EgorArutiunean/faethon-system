import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Document, Partner, Warehouse, api } from "../lib/api";

type DraftDocumentType = "incoming" | "outgoing" | "adjustment" | "transfer";

const today = new Date().toISOString().slice(0, 10);

export function Documents() {
  const { t } = useI18n();
  const { showToast } = useToast();
  const { can } = useAuth();
  const [rows, setRows] = useState<Document[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [error, setError] = useState("");
  const [draftForm, setDraftForm] = useState({
    document_type: "incoming" as DraftDocumentType,
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

  function load() {
    api.documents().then(setRows).catch((exc) => {
      setRows([]);
      setError(exc instanceof Error ? exc.message : t("apiLoadDocumentsError"));
    });
    api.partners().then(setPartners).catch((exc) => {
      const message = exc instanceof Error ? exc.message : t("apiLoadPartnersError");
      setError(message);
    });
    api.warehouses().then(setWarehouses).catch((exc) => {
      const message = exc instanceof Error ? exc.message : t("apiLoadWarehousesError");
      setError(message);
    });
  }

  function deleteDraft(documentId: number) {
    if (!window.confirm(t("deleteDraftConfirm"))) return;
    api.deleteDocument(documentId)
      .then(() => {
        showToast("success", t("deleteDraft"));
        load();
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
        load();
      })
      .catch((exc) => {
        const message = exc instanceof Error ? exc.message : String(exc);
        setError(message);
        showToast("error", message);
      });
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <PageScaffold title={t("documents")}>
      <div className="panel form-grid" style={{ marginBottom: 10 }}>
        <div className="field">
          <label>{t("type")}</label>
          <select value={draftForm.document_type} onChange={(event) => setDocumentType(event.target.value as DraftDocumentType)}>
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
          <select value={draftForm.warehouse_id} onChange={(event) => setDraftForm({ ...draftForm, warehouse_id: event.target.value })}>
            <option value="">{t("selectWarehouse")}</option>
            {warehouses.map((warehouse) => (
              <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>
            ))}
          </select>
        </div>
        {draftForm.document_type === "transfer" ? (
          <div className="field">
            <label>{t("destinationWarehouse")}</label>
            <select value={draftForm.destination_warehouse_id} onChange={(event) => setDraftForm({ ...draftForm, destination_warehouse_id: event.target.value })}>
              <option value="">{t("selectDestinationWarehouse")}</option>
              {warehouses.map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>
              ))}
            </select>
          </div>
        ) : null}
        {draftForm.document_type === "incoming" || draftForm.document_type === "outgoing" ? (
          <div className="field">
            <label>{draftForm.document_type === "incoming" ? t("supplier") : t("customer")}</label>
            <select value={draftForm.partner_id} onChange={(event) => setDraftForm({ ...draftForm, partner_id: event.target.value })}>
              <option value="">{t("selectPartner")}</option>
              {partnersForType.map((partner) => (
                <option key={partner.id} value={partner.id}>{partner.name}</option>
              ))}
            </select>
          </div>
        ) : null}
      </div>
      <div className="toolbar">
        <button className="button primary" title={!can("documents.create") ? t("noPermission") : ""} disabled={!can("documents.create")} onClick={createDraft}>{t("createDocument")}</button>
      </div>
      {error ? <div className="panel error-panel">{error}</div> : null}
      <DataTable<Document>
        rows={rows}
        emptyMessage={t("noDocuments")}
        searchable
        columns={[
          { key: "id", header: "ID", sortable: true, render: (row) => <Link to={`/documents/${row.id}`}>{row.id}</Link> },
          { key: "document_type", header: t("type"), sortable: true, render: (row) => formatCode(row.document_type, t) },
          { key: "number", header: t("number"), sortable: true },
          { key: "document_date", header: t("date"), sortable: true, render: (row) => formatDate(row.document_date) },
          { key: "status", header: t("status"), sortable: true, render: (row) => <StatusBadge status={row.status} label={formatCode(row.status, t)} /> },
          { key: "partner_name", header: t("partner"), sortable: true },
          { key: "warehouse_name", header: t("warehouse"), sortable: true },
          { key: "destination_warehouse_name", header: t("destinationWarehouse"), sortable: true },
          { key: "total_amount", header: t("total"), sortable: true, render: (row) => formatMoney(row.total_amount) },
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
      <p style={{ color: "#52616f", fontSize: 13 }}>
        TODO LEGACY_RULE_REQUIRED: document posting, cancellation, numbering, stock movement, and payment effects.
      </p>
    </PageScaffold>
  );
}
