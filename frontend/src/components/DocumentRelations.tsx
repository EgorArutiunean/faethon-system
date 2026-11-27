import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { api, Document, DocumentPaymentSummary, WarehouseTask } from "../lib/api";

export function DocumentRelations({ document }: { document: Document }) {
  const { can } = useAuth();
  const { t } = useI18n();
  const financialDocument = ["incoming", "outgoing"].includes(document.document_type);
  const showPayments = can("payments.read") && financialDocument;
  const showTasks = can("logistics.read");
  const [summary, setSummary] = useState<DocumentPaymentSummary | null>(null);
  const [tasks, setTasks] = useState<WarehouseTask[]>([]);
  const [paymentError, setPaymentError] = useState(false);
  const [taskError, setTaskError] = useState(false);

  useEffect(() => {
    let active = true;
    setSummary(null);
    setPaymentError(false);
    if (showPayments) {
      api.documentPaymentSummary(document.id)
        .then((value) => active && setSummary(value))
        .catch(() => active && setPaymentError(true));
    }
    return () => { active = false; };
  }, [document.id, document.posting_version, document.status, document.total_amount, showPayments]);

  useEffect(() => {
    let active = true;
    setTasks([]);
    setTaskError(false);
    if (showTasks) {
      api.warehouseTasks("", document.id)
        .then((values) => active && setTasks(values.filter((task) => task.posting_version === document.posting_version)))
        .catch(() => active && setTaskError(true));
    }
    return () => { active = false; };
  }, [document.id, document.posting_version, document.status, showTasks]);

  if (!showPayments && !showTasks) return null;
  const canCreate = summary && summary.document_status === "posted" && summary.partner_id !== null
    && summary.payment_type && Number(summary.outstanding_amount) > 0 && can("payments.create") && can("payments.allocate");

  return <section className="document-relations" aria-label={t("relatedOperations")}>
    <div className="document-relations-grid">
      {showPayments ? <section className="panel document-section" aria-label={t("documentPayments")} aria-busy={!summary && !paymentError}>
        <div className="document-section-title"><h2>{t("documentPayments")}</h2></div>
        {paymentError ? <p className="error-panel" role="alert">{t("relatedOperationsLoadError")}</p> : null}
        {summary ? <>
          <div className="document-payment-summary">
            <span>{t("documentPaid")} <strong data-testid="document-paid">{formatMoney(summary.paid_amount)}</strong></span>
            <span>{t("documentOutstanding")} <strong data-testid="document-outstanding">{formatMoney(summary.outstanding_amount)}</strong></span>
          </div>
          <p className="muted-note">{t("documentPaymentTotalsHint")}</p>
          <div className="document-relation-list">
            {summary.payments.map((payment) => <div className="document-relation-row" key={payment.id}>
              <span>{t("payment")} #{payment.id} · {formatDate(payment.payment_date)}</span>
              <span>{t("paymentForDocument")}: {formatMoney(payment.allocated_amount_for_document)}</span>
              <StatusBadge status={payment.status} label={formatCode(payment.status, t)} />
            </div>)}
            {summary.payments_count === 0 ? <p className="muted-note">{t("noRelatedPayments")}</p> : null}
          </div>
          <div className="workspace-command-bar">
            {canCreate ? <Link className="button primary" to={`/payments?document_id=${document.id}&create=${summary.payment_type}&page=1`}>
              {summary.payment_type === "customer_payment" ? t("createCustomerDocumentPayment") : t("createSupplierDocumentPayment")}
            </Link> : null}
            <Link className="button" to={`/payments?document_id=${document.id}&page=1`}>{t("openDocumentPayments")} ({summary.payments_count})</Link>
          </div>
          {can("payments.create") && !can("payments.allocate") ? <p className="muted-note">{t("allocationManagerOnly")}</p> : null}
        </> : null}
      </section> : null}
      {showTasks ? <section className="panel document-section" aria-label={t("relatedWarehouseTasks")}>
        <div className="document-section-title"><h2>{t("relatedWarehouseTasks")}</h2></div>
        {taskError ? <p className="error-panel" role="alert">{t("relatedOperationsLoadError")}</p> : null}
        <div className="document-relation-list">
          {tasks.map((task) => <div className="document-relation-row" key={task.id}>
            <span>{formatCode(task.task_type, t)} · {task.warehouse_name}</span>
            <StatusBadge status={task.status} label={formatCode(task.status, t)} />
            <Link className="button" to={`/logistics?task=${task.id}`}>{t("openWarehouseTask")} #{task.id}</Link>
          </div>)}
          {!taskError && tasks.length === 0 ? <p className="muted-note">{t("noRelatedWarehouseTasks")}</p> : null}
        </div>
      </section> : null}
    </div>
  </section>;
}
