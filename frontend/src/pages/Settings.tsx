import { useState } from "react";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { formatCode } from "../format";
import { useI18n } from "../i18n";
import { ImportSummary, api } from "../lib/api";
import { useToast } from "../toast";

const importTypes = [
  "products",
  "partners",
  "warehouses",
  "opening-stock",
  "opening-partner-balances"
];

export function Settings() {
  const { t } = useI18n();
  const { can } = useAuth();
  const { showToast } = useToast();
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [summaries, setSummaries] = useState<Record<string, ImportSummary | null>>({});
  const [error, setError] = useState("");

  function downloadTemplate(type: string) {
    api.importTemplate(type).then((blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${type}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      showToast("success", t("downloadTemplate"));
    }).catch((exc) => {
      const message = exc instanceof Error ? exc.message : String(exc);
      setError(message);
      showToast("error", message);
    });
  }

  function runDry(type: string) {
    const file = files[type];
    if (!file) {
      showToast("warning", t("selectFile"));
      return;
    }
    api.importDryRun(type, file).then((summary) => {
      setSummaries((current) => ({ ...current, [type]: summary }));
      showToast(summary.errors.length ? "warning" : "success", t("dryRun"));
    }).catch((exc) => {
      const message = exc instanceof Error ? exc.message : String(exc);
      setError(message);
      showToast("error", message);
    });
  }

  function applyImport(type: string) {
    const file = files[type];
    const summary = summaries[type];
    if (!file || !summary || summary.errors.length) {
      showToast("warning", t("dryRun"));
      return;
    }
    api.importApply(type, file).then((nextSummary) => {
      setSummaries((current) => ({ ...current, [type]: nextSummary }));
      showToast(nextSummary.errors.length ? "warning" : "success", t("applyImport"));
    }).catch((exc) => {
      const message = exc instanceof Error ? exc.message : String(exc);
      setError(message);
      showToast("error", message);
    });
  }

  if (!can("settings.manage")) {
    return (
      <PageScaffold title={t("settings")}>
        <div className="panel" style={{ padding: 12 }}>{t("noAccess")}</div>
      </PageScaffold>
    );
  }

  return (
    <PageScaffold title={t("settings")}>
      {error ? <div className="panel error-panel">{error}</div> : null}
      <div className="panel" style={{ padding: 12, marginBottom: 10 }}>
        <h2 style={{ fontSize: 16, margin: "0 0 10px" }}>{t("importLite")}</h2>
        <DataTable
          rows={importTypes.map((type) => ({ id: type, type, summary: summaries[type] }))}
          columns={[
            { key: "type", header: t("type"), render: (row) => formatCode(row.type, t) },
            {
              key: "file",
              header: t("selectFile"),
              render: (row) => <input type="file" accept=".csv,.xlsx" onChange={(event) => setFiles((current) => ({ ...current, [row.type]: event.target.files?.[0] ?? null }))} />
            },
            {
              key: "actions",
              header: t("actions"),
              render: (row) => (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button className="button" onClick={() => downloadTemplate(row.type)}>{t("downloadTemplate")}</button>
                  <button className="button" onClick={() => runDry(row.type)}>{t("dryRun")}</button>
                  <button className="button primary" disabled={!row.summary || row.summary.errors.length > 0} onClick={() => applyImport(row.type)}>{t("applyImport")}</button>
                </div>
              )
            },
            {
              key: "summary",
              header: t("status"),
              render: (row) => row.summary ? (
                <span>
                  {t("rowsTotal")}: {row.summary.rows_total}; {t("rowsValid")}: {row.summary.rows_valid}; {t("rowsInvalid")}: {row.summary.rows_invalid}; {t("createdRows")}: {row.summary.created}; {t("skippedRows")}: {row.summary.skipped}
                </span>
              ) : ""
            }
          ]}
        />
      </div>
      {Object.entries(summaries).map(([type, summary]) => summary ? (
        <div className="panel" key={type} style={{ padding: 12, marginBottom: 10 }}>
          <h3 style={{ fontSize: 15, margin: "0 0 8px" }}>{formatCode(type, t)}</h3>
          <div className="muted-note">{t("errors")}: {summary.errors.length}; {t("warnings")}: {summary.warnings.length}</div>
          {[...summary.errors, ...summary.warnings].map((issue, index) => (
            <div key={index} className={summary.errors.includes(issue) ? "error-panel" : "muted-note"}>
              row {issue.row} {issue.field ? `${issue.field}: ` : ""}{issue.message}
            </div>
          ))}
        </div>
      ) : null)}
    </PageScaffold>
  );
}
