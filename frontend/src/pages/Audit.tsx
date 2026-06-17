import { useEffect, useState } from "react";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { formatCode, formatDateTime } from "../format";
import { useI18n } from "../i18n";
import { AuditLog, api } from "../lib/api";

function params(values: Record<string, string>) {
  const search = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value) search.set(key, value);
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function Audit() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [rows, setRows] = useState<AuditLog[]>([]);
  const [entityType, setEntityType] = useState("");
  const [entityId, setEntityId] = useState("");
  const [action, setAction] = useState("");
  const [error, setError] = useState("");

  function load() {
    if (!can("audit.read")) return;
    api.audit(params({ entity_type: entityType, entity_id: entityId, action }))
      .then((nextRows) => {
        setRows(nextRows);
        setError("");
      })
      .catch((exc) => {
        setRows([]);
        setError(exc instanceof Error ? exc.message : String(exc));
      });
  }

  useEffect(() => {
    load();
  }, []);

  if (!can("audit.read")) {
    return (
      <PageScaffold title={t("auditLog")}>
        <div className="panel" style={{ padding: 12 }}>{t("noAccess")}</div>
      </PageScaffold>
    );
  }

  return (
    <PageScaffold title={t("auditLog")}>
      <div className="panel form-grid" style={{ marginBottom: 10 }}>
        <div className="field">
          <label>{t("entity")}</label>
          <select value={entityType} onChange={(event) => setEntityType(event.target.value)}>
            <option value="">{t("all")}</option>
            <option value="document">{t("document")}</option>
            <option value="payment">{t("payment")}</option>
            <option value="cash_operation">{t("cashOperation")}</option>
            <option value="product">{t("product")}</option>
            <option value="partner">{t("partner")}</option>
            <option value="warehouse">{t("warehouse")}</option>
            <option value="import">{t("importLite")}</option>
          </select>
        </div>
        <div className="field"><label>{t("entityId")}</label><input value={entityId} onChange={(event) => setEntityId(event.target.value)} /></div>
        <div className="field">
          <label>{t("action")}</label>
          <select value={action} onChange={(event) => setAction(event.target.value)}>
            <option value="">{t("all")}</option>
            <option value="create">{t("create")}</option>
            <option value="update">{t("update")}</option>
            <option value="post">{t("post")}</option>
            <option value="cancel">{t("cancel")}</option>
            <option value="delete">{t("delete")}</option>
            <option value="delete_draft">{t("deleteDraft")}</option>
            <option value="apply">{t("apply")}</option>
          </select>
        </div>
        <div className="field"><label>&nbsp;</label><button className="button primary" onClick={load}>{t("filter")}</button></div>
      </div>
      {error ? <div className="panel error-panel">{error}</div> : null}
      <DataTable<AuditLog>
        rows={rows}
        emptyMessage={t("noRows")}
        searchable
        columns={[
          { key: "created_at", header: t("date"), sortable: true, render: (row) => formatDateTime(row.created_at) },
          { key: "entity_type", header: t("entity"), sortable: true, render: (row) => formatCode(row.entity_type, t) },
          { key: "entity_id", header: t("entityId"), sortable: true },
          { key: "action", header: t("action"), sortable: true, render: (row) => formatCode(row.action, t) },
          { key: "details", header: t("note") },
          { key: "actor_user_id", header: t("actorUser"), sortable: true }
        ]}
      />
    </PageScaffold>
  );
}
