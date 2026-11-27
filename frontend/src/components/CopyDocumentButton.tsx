import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { api, type Document } from "../lib/api";
import { useToast } from "../toast";

type CopyDocumentButtonProps = {
  documentId: number;
  documentNumber?: string | null;
  hasUnsavedChanges?: boolean;
  disabled?: boolean;
  onCopied: (document: Document) => void;
};

function localToday() {
  const value = new Date();
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

export function CopyDocumentButton({ documentId, documentNumber, hasUnsavedChanges = false, disabled = false, onCopied }: CopyDocumentButtonProps) {
  const { can } = useAuth();
  const { t } = useI18n();
  const { showToast } = useToast();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const copyingRef = useRef(false);
  const [open, setOpen] = useState(false);
  const [documentDate, setDocumentDate] = useState(localToday);
  const [copying, setCopying] = useState(false);
  const [error, setError] = useState("");
  const allowed = can("documents.read") && can("documents.create") && can("documents.update");

  useEffect(() => {
    if (open && !dialogRef.current?.open) dialogRef.current?.showModal();
    if (!open && dialogRef.current?.open) dialogRef.current.close();
  }, [open]);

  async function copy() {
    if (copyingRef.current || !allowed || disabled) return;
    if (!documentDate) {
      setError(t("selectDate"));
      return;
    }
    copyingRef.current = true;
    setCopying(true);
    setError("");
    let copied: Document;
    try {
      copied = await api.copyDocument(documentId, { document_date: documentDate });
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : String(exc);
      setError(message);
      showToast("error", message);
      return;
    } finally {
      copyingRef.current = false;
      setCopying(false);
    }
    setOpen(false);
    showToast("success", t("copiedDocumentSuccess"));
    onCopied(copied);
  }

  return <>
    <button
      type="button"
      data-testid="document-copy"
      className="button"
      disabled={disabled || !allowed || copying}
      title={!allowed ? t("noPermission") : ""}
      onClick={() => { setError(""); setDocumentDate(localToday()); setOpen(true); }}
    >{t("copyDocument")}</button>
    {createPortal(<dialog
      ref={dialogRef}
      className="confirm-dialog"
      aria-labelledby="copy-document-title"
      onCancel={(event) => { event.preventDefault(); if (!copyingRef.current) setOpen(false); }}
    >
      <form onSubmit={(event) => { event.preventDefault(); void copy(); }}>
        <h2 id="copy-document-title">{t("copyDocument")}: {documentNumber || `#${documentId}`}</h2>
        <p>{t("copyDocumentHint")}</p>
        {hasUnsavedChanges ? <p role="status">{t("copySavedVersionWarning")}</p> : null}
        <div className="field">
          <label htmlFor="copy-document-date">{t("date")}</label>
          <input id="copy-document-date" data-testid="document-copy-date" type="date" value={documentDate} onChange={(event) => setDocumentDate(event.target.value)} required disabled={copying} autoFocus />
        </div>
        {error ? <p className="error-panel" role="alert">{error}</p> : null}
        <div className="confirm-dialog-actions">
          <button type="button" className="button" disabled={copying} onClick={() => setOpen(false)}>{t("dismissAction")}</button>
          <button type="submit" className="button primary" data-testid="document-copy-submit" disabled={copying}>{copying ? t("loading") : t("copyDocument")}</button>
        </div>
      </form>
    </dialog>, window.document.body)}
  </>;
}
