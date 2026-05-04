import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Cash } from "./pages/Cash";
import { Dashboard } from "./pages/Dashboard";
import { DocumentEditor } from "./pages/DocumentEditor";
import { Documents } from "./pages/Documents";
import { Partners } from "./pages/Partners";
import { PartnerStatement } from "./pages/PartnerStatement";
import { Payments } from "./pages/Payments";
import { Products } from "./pages/Products";
import { Reports } from "./pages/Reports";
import { Settings } from "./pages/Settings";
import { Login } from "./pages/Login";
import { Stock } from "./pages/Stock";
import { Warehouses } from "./pages/Warehouses";
import { I18nProvider } from "./i18n";
import { AuthProvider } from "./auth";
import { ToastProvider } from "./toast";
import "./styles.css";

const router = createBrowserRouter([
  { path: "/login", element: <Login /> },
  {
    path: "/",
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <Dashboard /> },
          { path: "products", element: <Products /> },
          { path: "partners", element: <Partners /> },
          { path: "partners/:id/statement", element: <PartnerStatement /> },
          { path: "warehouses", element: <Warehouses /> },
          { path: "documents", element: <Documents /> },
          { path: "documents/:id", element: <DocumentEditor /> },
          { path: "stock", element: <Stock /> },
          { path: "payments", element: <Payments /> },
          { path: "cash", element: <Cash /> },
          { path: "reports", element: <Reports /> },
          { path: "settings", element: <Settings /> }
        ]
      }
    ]
  }
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <I18nProvider>
      <AuthProvider>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </AuthProvider>
    </I18nProvider>
  </React.StrictMode>
);
