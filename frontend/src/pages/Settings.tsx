import { useEffect, useState } from "react";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { formatCode } from "../format";
import { useI18n } from "../i18n";
import { ImportSummary, ManagedUser, Role, api } from "../lib/api";
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
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [roleNames, setRoleNames] = useState<string[]>(["viewer"]);
  const [error, setError] = useState("");

  function loadUsers() {
    if (!can("users.manage")) return;
    Promise.all([api.users(), api.roles()])
      .then(([nextUsers, nextRoles]) => {
        setUsers(nextUsers);
        setRoles(nextRoles);
      })
      .catch((exc) => {
        const message = exc instanceof Error ? exc.message : String(exc);
        setError(message);
        showToast("error", message);
      });
  }

  function resetUserForm() {
    setEditingUserId(null);
    setEmail("");
    setFullName("");
    setPassword("");
    setIsActive(true);
    setRoleNames(["viewer"]);
  }

  function editUser(row: ManagedUser) {
    setEditingUserId(row.id);
    setEmail(row.email);
    setFullName(row.full_name ?? "");
    setPassword("");
    setIsActive(row.is_active);
    setRoleNames(row.role_names.length ? row.role_names : ["viewer"]);
  }

  function toggleRole(roleName: string) {
    setRoleNames((current) => {
      if (current.includes(roleName)) {
        const next = current.filter((name) => name !== roleName);
        return next.length ? next : current;
      }
      return [...current, roleName];
    });
  }

  function saveUser() {
    if (!email || (!editingUserId && !password) || roleNames.length === 0) {
      showToast("warning", t("selectRoles"));
      return;
    }
    const payload = {
      email,
      full_name: fullName || null,
      is_active: isActive,
      role_names: roleNames,
      ...(password ? { password } : {}),
    };
    const request = editingUserId
      ? api.updateUser(editingUserId, payload)
      : api.createUser({ ...payload, password });
    request
      .then(() => {
        resetUserForm();
        loadUsers();
        showToast("success", t("saved"));
      })
      .catch((exc) => {
        const message = exc instanceof Error ? exc.message : String(exc);
        setError(message);
        showToast("error", message);
      });
  }

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

  useEffect(() => {
    loadUsers();
  }, []);

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
      {can("users.manage") ? (
        <div className="panel" style={{ padding: 12, marginBottom: 10 }}>
          <h2 style={{ fontSize: 16, margin: "0 0 10px" }}>{t("users")}</h2>
          <div className="form-grid" style={{ marginBottom: 10 }}>
            <div className="field"><label>{t("email")}</label><input value={email} onChange={(event) => setEmail(event.target.value)} /></div>
            <div className="field"><label>{t("name")}</label><input value={fullName} onChange={(event) => setFullName(event.target.value)} /></div>
            <div className="field"><label>{editingUserId ? t("newPassword") : t("password")}</label><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></div>
            <div className="field"><label>{t("activeUser")}</label><input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} /></div>
            <div className="field" style={{ minWidth: 240 }}>
              <label>{t("roles")}</label>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", paddingTop: 4 }}>
                {roles.map((role) => (
                  <label key={role.id} style={{ display: "flex", gap: 4, alignItems: "center", fontSize: 13 }}>
                    <input type="checkbox" checked={roleNames.includes(role.name)} onChange={() => toggleRole(role.name)} />
                    {formatCode(role.name, t)}
                  </label>
                ))}
              </div>
            </div>
            <div className="field">
              <label>&nbsp;</label>
              <div style={{ display: "flex", gap: 6 }}>
                <button className="button primary" onClick={saveUser}>{editingUserId ? t("save") : t("create")}</button>
                {editingUserId ? <button className="button" onClick={resetUserForm}>{t("cancel")}</button> : null}
              </div>
            </div>
          </div>
          <DataTable<ManagedUser>
            rows={users}
            emptyMessage={t("noRows")}
            searchable
            columns={[
              { key: "email", header: t("email"), sortable: true },
              { key: "full_name", header: t("name"), sortable: true },
              { key: "role_names", header: t("roles"), render: (row) => row.role_names.map((role) => formatCode(role, t)).join(", ") },
              { key: "is_active", header: t("activeUser"), sortable: true, render: (row) => row.is_active ? t("yes") : t("no") },
              { key: "actions", header: t("actions"), render: (row) => <button className="button" onClick={() => editUser(row)}>{t("edit")}</button> }
            ]}
          />
        </div>
      ) : null}
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
