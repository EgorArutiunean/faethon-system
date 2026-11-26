import { useI18n } from "../i18n";
import { LocalDraftStatus } from "../hooks/useLocalDraft";

export function DraftRecoveryNotice({ draft }: { draft: LocalDraftStatus }) {
  const { t } = useI18n();
  if (!draft.recoveredAt && !draft.stale && !draft.storageError) return null;
  return <div className="panel draft-recovery-notice" role={draft.stale || draft.storageError ? "alert" : "status"}>
    <div>
      <strong>{t(draft.stale ? "localDraftStale" : draft.storageError ? "localDraftStorageError" : "localDraftRestored")}</strong>
      {draft.recoveredAt && !draft.stale ? <small>{t("localDraftRestoredHint")}</small> : null}
    </div>
    {draft.stale || draft.recoveredAt ? <button className="button" onClick={draft.discard}>{t(draft.stale ? "deleteLocalDraft" : "discardRecoveredInput")}</button> : null}
  </div>;
}
