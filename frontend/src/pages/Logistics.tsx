import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, ExternalLink, Play, RefreshCw, RotateCcw } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth";
import { PageScaffold } from "../components/PageScaffold";
import { formatCode, formatDate, formatDateTime, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { WarehouseTask, api } from "../lib/api";
import { useToast } from "../toast";

const statusFilters = ["", "pending", "in_transit", "in_progress", "needs_review", "blocked", "completed", "cancelled"];

type LineDraft = Record<number, { actual: string; comment: string }>;

function formatQuantity(value?: string | null) {
  if (value === undefined || value === null || value === "") return "";
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("ru-RU", { maximumFractionDigits: 3 })
    : value;
}

export function Logistics() {
  const { t } = useI18n();
  const { user, can } = useAuth();
  const { showToast } = useToast();
  const [tasks, setTasks] = useState<WarehouseTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<WarehouseTask | null>(null);
  const [status, setStatus] = useState("");
  const [lineDraft, setLineDraft] = useState<LineDraft>({});
  const [reviewNote, setReviewNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function load(preferredTaskId?: number) {
    if (!can("logistics.read")) return;
    setError("");
    api.warehouseTasks(status)
      .then((loaded) => {
        setTasks(loaded);
        setSelectedTask((current) => {
          const targetId = preferredTaskId ?? current?.id;
          return loaded.find((task) => task.id === targetId) ?? loaded[0] ?? null;
        });
      })
      .catch((exc) => {
        setTasks([]);
        setSelectedTask(null);
        setError(exc instanceof Error ? exc.message : t("apiLoadTasksError"));
      });
  }

  useEffect(() => {
    load();
  }, [status, user?.id]);

  useEffect(() => {
    if (!selectedTask) {
      setLineDraft({});
      return;
    }
    setLineDraft(Object.fromEntries(selectedTask.lines.map((line) => [
      line.id,
      {
        actual: line.actual_quantity ?? line.expected_quantity,
        comment: line.comment ?? ""
      }
    ])));
    setReviewNote("");
  }, [selectedTask?.id, selectedTask?.status]);

  const taskCounts = useMemo(() => tasks.reduce<Record<string, number>>((counts, task) => {
    counts[task.status] = (counts[task.status] ?? 0) + 1;
    return counts;
  }, {}), [tasks]);

  function applyUpdatedTask(updated: WarehouseTask) {
    setSelectedTask(updated);
    setTasks((current) => {
      if (status && updated.status !== status) {
        return current.filter((task) => task.id !== updated.id);
      }
      return current.map((task) => task.id === updated.id ? updated : task);
    });
    showToast("success", t("taskUpdated"));
  }

  async function runAction(action: () => Promise<WarehouseTask>) {
    setBusy(true);
    setError("");
    try {
      applyUpdatedTask(await action());
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : t("apiUpdateTaskError");
      setError(message);
      showToast("error", message);
    } finally {
      setBusy(false);
    }
  }

  function confirmSelectedTask() {
    if (!selectedTask) return;
    const lines = selectedTask.lines.map((line) => ({
      line_id: line.id,
      actual_quantity: lineDraft[line.id]?.actual ?? "",
      comment: lineDraft[line.id]?.comment.trim() || null
    }));
    const invalidQuantity = lines.some((line) => line.actual_quantity === "" || Number(line.actual_quantity) < 0);
    if (invalidQuantity) {
      setError(t("invalidQuantity"));
      return;
    }
    const missingComment = selectedTask.lines.some((line) => {
      const draft = lineDraft[line.id];
      return Number(draft?.actual) !== Number(line.expected_quantity) && !draft?.comment.trim();
    });
    if (missingComment) {
      setError(t("discrepancyCommentRequired"));
      return;
    }
    runAction(() => api.confirmWarehouseTask(selectedTask.id, lines));
  }

  function returnSelectedTask() {
    if (!selectedTask) return;
    if (reviewNote.trim().length < 3) {
      setError(t("reviewNoteRequired"));
      return;
    }
    runAction(() => api.returnWarehouseTask(selectedTask.id, reviewNote.trim()));
  }

  if (!can("logistics.read")) {
    return (
      <PageScaffold title={t("warehouseTasks")}>
        <div className="panel" style={{ padding: 12 }}>{t("noAccess")}</div>
      </PageScaffold>
    );
  }

  return (
    <PageScaffold title={t("warehouseTasks")}>
      <div className="logistics-scope-row">
        <span className="muted-note">
          {t("assignedWarehouses")}: {can("logistics.review") ? t("allWarehouses") : user?.warehouse_names.join(", ") || t("notSelected")}
        </span>
        <button className="button icon-text-button" onClick={() => load(selectedTask?.id)} title={t("sync")}>
          <RefreshCw size={16} aria-hidden="true" />
          {t("sync")}
        </button>
      </div>

      <div className="logistics-status-tabs" role="tablist" aria-label={t("status")}>
        {statusFilters.map((filter) => (
          <button
            key={filter || "all"}
            type="button"
            className={status === filter ? "active" : ""}
            onClick={() => setStatus(filter)}
            role="tab"
            aria-selected={status === filter}
          >
            {filter ? formatCode(filter, t) : t("all")}
            {!status && filter ? <span>{taskCounts[filter] ?? 0}</span> : null}
          </button>
        ))}
      </div>

      {error ? <div className="panel error-panel logistics-error">{error}</div> : null}

      <div className="logistics-workspace">
        <section className="panel logistics-queue" aria-label={t("warehouseTasks")}>
          <div className="logistics-queue-header">
            <strong>{t("warehouseTasks")}</strong>
            <span>{tasks.length}</span>
          </div>
          <div className="logistics-task-list">
            {tasks.map((task) => (
              <button
                type="button"
                key={task.id}
                className={`logistics-task-row${selectedTask?.id === task.id ? " selected" : ""}`}
                onClick={() => setSelectedTask(task)}
              >
                <span className="logistics-task-main">
                  <b>{formatCode(task.task_type, t)}</b>
                  <small>{task.document_number || `#${task.document_id}`} · {formatDate(task.document_date)}</small>
                </span>
                <span className="logistics-task-meta">
                  <StatusBadge status={task.status} label={formatCode(task.status, t)} />
                  <small>{task.warehouse_name}</small>
                </span>
              </button>
            ))}
            {!tasks.length ? <div className="logistics-empty">{t("noWarehouseTasks")}</div> : null}
          </div>
        </section>

        <section className="panel logistics-task-detail">
          {selectedTask ? (
            <>
              <header className="logistics-detail-header">
                <div>
                  <span>{formatCode(selectedTask.task_type, t)}</span>
                  <h2>{selectedTask.document_number || `#${selectedTask.document_id}`}</h2>
                  <p>{formatDate(selectedTask.document_date)} · {selectedTask.warehouse_name}</p>
                </div>
                <StatusBadge status={selectedTask.status} label={formatCode(selectedTask.status, t)} />
              </header>

              <dl className="logistics-facts">
                <div><dt>{t("partner")}</dt><dd>{selectedTask.partner_name || "-"}</dd></div>
                <div><dt>{t("assignedTo")}</dt><dd>{selectedTask.assigned_to_name || t("notSelected")}</dd></div>
                <div><dt>{t("taskVersion")}</dt><dd>{selectedTask.posting_version}</dd></div>
                <div><dt>{t("positions")}</dt><dd>{selectedTask.lines.length}</dd></div>
              </dl>

              <div className="logistics-line-table-wrap">
                <table className="data-table logistics-line-table">
                  <thead>
                    <tr>
                      <th>{t("product")}</th>
                      <th>{t("expectedQuantity")}</th>
                      <th>{t("actualQuantity")}</th>
                      <th>{t("salePrice")}</th>
                      <th>{t("sum")}</th>
                      <th>{t("discrepancyComment")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedTask.lines.map((line) => {
                      const editable = selectedTask.status === "in_progress" && can("logistics.process");
                      const differs = Number(lineDraft[line.id]?.actual) !== Number(line.expected_quantity);
                      return (
                        <tr key={line.id} className={differs ? "has-discrepancy" : ""}>
                          <td>{line.product_name}</td>
                          <td>{formatQuantity(line.expected_quantity)}</td>
                          <td>
                            {editable ? (
                              <input
                                data-testid={`task-line-actual-${line.id}`}
                                className="logistics-quantity-input"
                                type="number"
                                min="0"
                                step="0.001"
                                value={lineDraft[line.id]?.actual ?? ""}
                                onChange={(event) => setLineDraft((current) => ({
                                  ...current,
                                  [line.id]: { ...current[line.id], actual: event.target.value }
                                }))}
                              />
                            ) : formatQuantity(line.actual_quantity ?? line.expected_quantity)}
                          </td>
                          <td>{formatMoney(line.sale_price)}</td>
                          <td>{formatMoney(line.sale_total)}</td>
                          <td>
                            {editable ? (
                              <input
                                className="logistics-comment-input"
                                value={lineDraft[line.id]?.comment ?? ""}
                                onChange={(event) => setLineDraft((current) => ({
                                  ...current,
                                  [line.id]: { ...current[line.id], comment: event.target.value }
                                }))}
                                placeholder={differs ? t("discrepancyCommentRequired") : ""}
                              />
                            ) : line.comment || "-"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="logistics-actions">
                {(selectedTask.status === "pending" || selectedTask.status === "in_transit") && can("logistics.process") ? (
                  <button
                    data-testid="start-warehouse-task"
                    className="button primary icon-text-button"
                    disabled={busy}
                    onClick={() => runAction(() => api.startWarehouseTask(selectedTask.id))}
                  >
                    <Play size={16} aria-hidden="true" />
                    {t("takeTask")}
                  </button>
                ) : null}
                {selectedTask.status === "in_progress" && can("logistics.process") ? (
                  <button
                    data-testid="confirm-warehouse-task"
                    className="button primary icon-text-button"
                    disabled={busy}
                    onClick={confirmSelectedTask}
                  >
                    <CheckCircle2 size={16} aria-hidden="true" />
                    {t("confirmTask")}
                  </button>
                ) : null}
                {can("documents.read") ? (
                  <Link className="button icon-text-button" to={`/documents/${selectedTask.document_id}`}>
                    <ExternalLink size={16} aria-hidden="true" />
                    {selectedTask.status === "needs_review" ? t("correctSourceDocument") : t("document")}
                  </Link>
                ) : null}
              </div>

              {selectedTask.status === "needs_review" && can("logistics.review") ? (
                <div className="logistics-review">
                  <div className="field">
                    <label>{t("reviewNote")}</label>
                    <textarea value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} />
                  </div>
                  <button className="button icon-text-button" disabled={busy} onClick={returnSelectedTask}>
                    <RotateCcw size={16} aria-hidden="true" />
                    {t("returnForClarification")}
                  </button>
                </div>
              ) : null}

              <div className="logistics-history">
                <h3>{t("taskHistory")}</h3>
                {selectedTask.events.map((event) => (
                  <div key={event.id} className="logistics-history-row">
                    <span>{formatDateTime(event.created_at)}</span>
                    <b>{formatCode(event.event_type, t)}</b>
                    <span>{event.actor_name || "Система"}</span>
                    {event.note ? <p>{event.note}</p> : null}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="logistics-empty">{t("noWarehouseTasks")}</div>
          )}
        </section>
      </div>
    </PageScaffold>
  );
}
