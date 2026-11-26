import { useCallback, useEffect, useRef, useState } from "react";

import { useI18n } from "../i18n";

type Confirmation = {
  message: string;
  confirmLabel: string;
  danger?: boolean;
};

type PendingConfirmation = Confirmation & { resolve: (confirmed: boolean) => void };

export function useConfirmDialog() {
  const { t } = useI18n();
  const [pending, setPending] = useState<PendingConfirmation | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);

  const ask = useCallback((options: Confirmation) => new Promise<boolean>((resolve) => {
    setPending({ ...options, resolve });
  }), []);

  const finish = useCallback((confirmed: boolean) => {
    pending?.resolve(confirmed);
    setPending(null);
  }, [pending]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (pending && !dialog.open) dialog.showModal();
    if (!pending && dialog.open) dialog.close();
  }, [pending]);

  const dialog = (
    <dialog className="confirm-dialog" ref={dialogRef} aria-labelledby="confirm-dialog-title" onCancel={(event) => { event.preventDefault(); finish(false); }}>
      <h2 id="confirm-dialog-title">{t("confirmAction")}</h2>
      <p>{pending?.message}</p>
      <div className="confirm-dialog-actions">
        <button className="button" autoFocus onClick={() => finish(false)}>{t("dismissAction")}</button>
        <button className={`button ${pending?.danger ? "danger" : "primary"}`} onClick={() => finish(true)}>{pending?.confirmLabel}</button>
      </div>
    </dialog>
  );

  return { ask, dialog };
}
