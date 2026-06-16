import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Document, api } from "../lib/api";

export function Documents() {
  const { t } = useI18n();
  const { showToast } = useToast();
  const { can } = useAuth();
  const [rows, setRows] = useState<Document[]>([]);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  function createDraft() {
    api
      .createDocument({
        document_type: "incoming",
        document_date: new Date().toISOString().slice(0, 10),
        status: "draft",
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
        <div className="field"><label>{t("type")}</label><select><option>{t("incoming")}</option><option>{t("outgoing")}</option><option>{t("adjustment")}</option><option>{t("transfer")}</option></select></div>
        <div className="field"><label>{t("number")}</label><input /></div>
        <div className="field"><label>{t("date")}</label><input type="date" /></div>
        <div className="field"><label>{t("status")}</label><select><option>{t("draft")}</option><option>{t("posted")}</option><option>{t("cancelled")}</option></select></div>
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
