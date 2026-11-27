import { FormEvent, useState } from "react";

import { useI18n } from "../i18n";
import { JournalState, JournalView, journalViewMatches } from "../lib/journalState";

type Props<Sort extends string> = {
  state: JournalState<Sort>;
  views: JournalView<Sort>[];
  saveView: (name: string) => boolean;
  deleteView: (id: string) => boolean;
  applyView: (view: JournalView<Sort>) => void;
};

export function JournalViews<Sort extends string>({ state, views, saveView, deleteView, applyView }: Props<Sort>) {
  const { t } = useI18n();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const current = views.find((view) => journalViewMatches(view.state, state));

  function save(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) { setError(t("nameRequired")); return; }
    if (views.some((view) => view.name.toLocaleLowerCase() === trimmed.toLocaleLowerCase())) { setError(t("journalViewNameExists")); return; }
    if (views.length >= 50) { setError(t("journalViewLimit")); return; }
    if (!saveView(trimmed)) { setError(t("journalViewSaveError")); return; }
    setEditing(false);
    setName("");
    setError("");
  }

  return <div className="journal-views">
    <div className="journal-views-controls">
      <label>{t("journalView")}
        <select aria-label={t("savedJournalView")} value={current?.id ?? ""} onChange={(event) => {
          const view = views.find((item) => item.id === event.target.value);
          if (view) applyView(view);
          setError("");
        }}>
          <option value="" disabled>{t("currentJournalSettings")}</option>
          {views.map((view) => <option key={view.id} value={view.id}>{view.name}</option>)}
        </select>
      </label>
      <button className="button" aria-expanded={editing} onClick={() => { setEditing((open) => !open); setError(""); }}>{t("saveJournalView")}</button>
      {current ? <button className="button" onClick={() => {
        if (!deleteView(current.id)) setError(t("journalViewSaveError"));
      }}>{t("deleteJournalView")}</button> : null}
      <small>{t("journalViewsHint")}</small>
    </div>
    {editing ? <form className="journal-view-form" onSubmit={save}>
      <label>{t("journalViewName")}<input autoFocus value={name} maxLength={80} onChange={(event) => { setName(event.target.value); setError(""); }} aria-invalid={Boolean(error)} /></label>
      <button className="button primary" type="submit">{t("save")}</button>
      <button className="button" type="button" onClick={() => { setEditing(false); setError(""); }}>{t("close")}</button>
    </form> : null}
    {error ? <small className="field-error" role="alert">{error}</small> : null}
  </div>;
}
