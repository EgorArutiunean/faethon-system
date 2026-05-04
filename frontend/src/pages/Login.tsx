import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../auth";
import { useI18n } from "../i18n";

export function Login() {
  const { t } = useI18n();
  const { login, user } = useAuth();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");

  if (user) {
    return <Navigate to="/" replace />;
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    login(email, password).catch(() => setError(t("loginError")));
  }

  return (
    <div className="login-page">
      <form className="panel login-panel" onSubmit={submit}>
        <h1>{t("loginTitle")}</h1>
        <p className="muted-note">{t("loginHint")}</p>
        <div className="field">
          <label>{t("email")}</label>
          <input value={email} onChange={(event) => setEmail(event.target.value)} />
        </div>
        <div className="field">
          <label>{t("password")}</label>
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </div>
        {error ? <div className="panel error-panel">{error}</div> : null}
        <button className="button primary" type="submit">{t("signIn")}</button>
      </form>
    </div>
  );
}
