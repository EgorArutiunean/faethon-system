import type { ReactNode } from "react";

type PageScaffoldProps = {
  title: string;
  children: ReactNode;
};

export function PageScaffold({ title, children }: PageScaffoldProps) {
  return (
    <>
      <div className="page-heading"><h1>{title}</h1></div>
      {children}
    </>
  );
}
