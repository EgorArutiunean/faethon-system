import type { ReactNode } from "react";
import { useI18n } from "../i18n";

type PageScaffoldProps = {
  title: string;
  children: ReactNode;
};

export function PageScaffold({ title, children }: PageScaffoldProps) {
  const { t } = useI18n();
  return (
    <>
      <div className="toolbar">
        <h1 style={{ fontSize: 20, margin: "0 12px 0 0" }}>{title}</h1>
        <input className="search" placeholder={t("search")} />
        <button className="button">{t("filter")}</button>
        <button className="button">{t("export")}</button>
      </div>
      {children}
    </>
  );
}
