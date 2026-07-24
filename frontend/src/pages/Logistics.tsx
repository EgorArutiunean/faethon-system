import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../auth";
import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { LogisticsDocument, LogisticsDocumentLine, api } from "../lib/api";

type LogisticsRow = LogisticsDocumentLine & {
  row_id: string;
  document_number: string;
  document_date: string;
  document_type: string;
  document_status: string;
  partner_name?: string | null;
  warehouse_route: string;
};

export function Logistics() {
  const { t } = useI18n();
  const { user, can } = useAuth();
  const [documents, setDocuments] = useState<LogisticsDocument[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!can("logistics.read")) return;
    setError("");
    api.logisticsDocuments(status)
      .then(setDocuments)
      .catch((exc) => setError(exc instanceof Error ? exc.message : String(exc)));
  }, [status]);

  const rows = useMemo<LogisticsRow[]>(() => documents.flatMap((document) => (
    document.lines.map((line) => ({
      ...line,
      row_id: `${document.id}-${line.id}`,
      document_number: document.number || String(document.id),
      document_date: document.document_date,
      document_type: document.document_type,
      document_status: document.status,
      partner_name: document.partner_name,
      warehouse_route: document.destination_warehouse_name
        ? `${document.warehouse_name || ""} -> ${document.destination_warehouse_name}`
        : document.warehouse_name || ""
    }))
  )), [documents]);

  if (!can("logistics.read")) {
    return (
      <PageScaffold title={t("logistics")}>
        <div className="panel" style={{ padding: 12 }}>{t("noAccess")}</div>
      </PageScaffold>
    );
  }

  return (
    <PageScaffold title={t("logistics")}>
      <div className="toolbar">
        <div className="field">
          <label>{t("status")}</label>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">{t("all")}</option>
            <option value="draft">{t("draft")}</option>
            <option value="posted">{t("posted")}</option>
            <option value="cancelled">{t("cancelled")}</option>
          </select>
        </div>
        <span className="muted-note">
          {t("assignedWarehouses")}: {user?.warehouse_names.join(", ") || t("notSelected")}
        </span>
      </div>
      {error ? <div className="panel error-panel">{error}</div> : null}
      <DataTable<LogisticsRow>
        rows={rows}
        emptyMessage={t("noDocuments")}
        searchable
        columns={[
          { key: "document_date", header: t("date"), sortable: true, render: (row) => formatDate(row.document_date) },
          { key: "document_number", header: t("number"), sortable: true },
          { key: "document_type", header: t("type"), sortable: true, render: (row) => formatCode(row.document_type, t) },
          { key: "partner_name", header: t("partner"), sortable: true },
          { key: "warehouse_route", header: t("warehouse"), sortable: true },
          { key: "product_name", header: t("product"), sortable: true },
          { key: "quantity", header: t("quantity"), sortable: true },
          { key: "sale_price", header: t("salePrice"), sortable: true, render: (row) => formatMoney(row.sale_price) },
          { key: "sale_total", header: t("sum"), sortable: true, render: (row) => formatMoney(row.sale_total) },
          {
            key: "document_status",
            header: t("status"),
            sortable: true,
            render: (row) => <StatusBadge status={row.document_status} label={formatCode(row.document_status, t)} />
          }
        ]}
      />
    </PageScaffold>
  );
}
