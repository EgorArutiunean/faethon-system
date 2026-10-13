import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { useAuth } from "../auth";
import { useI18n } from "../i18n";

export function ChangePassword() {
  const { t } = useI18n();
  const { changePassword, loading, logout, user } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return <div style={{ padding: 18 }}>{t("loading")}</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!user.must_change_password) {
    return <Navigate to="/" replace />;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (newPassword.length < 12) {
      setError(t("passwordMinimum"));
      return;
    }
    if (newPassword !== confirmPassword) {
      setError(t("passwordMismatch"));
      return;
    }

    setSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword);
      navigate("/", { replace: true });
    } catch {
      setError(t("passwordChangeError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <form className="panel login-panel" onSubmit={submit}>
        <h1>{t("passwordChangeTitle")}</h1>
        <p className="muted-note">{t("passwordChangeRequired")}</p>
        <div className="field">
          <label htmlFor="current-password">{t("currentPassword")}</label>
          <input id="current-password" autoComplete="current-password" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="new-password">{t("newPassword")}</label>
          <input id="new-password" autoComplete="new-password" type="password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="confirm-password">{t("confirmPassword")}</label>
          <input id="confirm-password" autoComplete="new-password" type="password" minLength={12} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required />
        </div>
        {error ? <div className="panel error-panel">{error}</div> : null}
        <button className="button primary" type="submit" disabled={submitting}>{t("changePassword")}</button>
        <button className="button" type="button" onClick={logout}>{t("logout")}</button>
      </form>
    </div>
  );
}
