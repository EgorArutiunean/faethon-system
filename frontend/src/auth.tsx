import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { CurrentUser, api } from "./lib/api";

type AuthContextValue = {
  token: string | null;
  user: CurrentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  can: (permission: string) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("buy-modern-token"));
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(Boolean(token));

  useEffect(() => {
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    api.me()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("buy-modern-token");
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  const value = useMemo<AuthContextValue>(() => ({
    token,
    user,
    loading,
    async login(email: string, password: string) {
      const response = await api.login({ email, password });
      localStorage.setItem("buy-modern-token", response.access_token);
      setToken(response.access_token);
    },
    logout() {
      localStorage.removeItem("buy-modern-token");
      setToken(null);
      setUser(null);
    },
    can(permission: string) {
      return user?.permissions.includes(permission) ?? false;
    },
  }), [loading, token, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
