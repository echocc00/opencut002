"use client";
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { apiFetch, getToken, setToken, clearToken, USER_KEY } from "./api";

interface AuthUser {
  id: number;
  email: string;
  username: string;
  is_admin: boolean;
}

interface AuthCtx {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    // 用 localStorage 缓存的 user + 验证 token
    try {
      const cached = localStorage.getItem(USER_KEY);
      if (cached) setUser(JSON.parse(cached));
    } catch {
      /* ignore */
    }
    apiFetch<AuthUser>("/api/auth/me")
      .then(setUser)
      .catch(() => {
        clearToken();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const data = await apiFetch<{ access_token: string; user: AuthUser }>(
      "/api/auth/login",
      { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }) },
    );
    setToken(data.access_token, data.user);
    setUser(data.user);
  };

  const register = async (email: string, username: string, password: string) => {
    const data = await apiFetch<{ access_token: string; user: AuthUser }>(
      "/api/auth/register",
      { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, username, password }) },
    );
    setToken(data.access_token, data.user);
    setUser(data.user);
  };

  const logout = () => {
    clearToken();
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <Ctx.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth 必须在 AuthProvider 内使用");
  return ctx;
}
