import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import axios, { AxiosInstance } from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export interface User {
  id?: string;
  email: string;
  name?: string;
  role?: string;
}

interface LoginResult {
  requires_2fa: boolean;
  temp_token?: string;
  user?: User;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  api: AxiosInstance;
  login: (email: string, password: string) => Promise<LoginResult>;
  logout: () => void;
  setAuth: (token: string, user: User) => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser]   = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("roddos_token"));
  const [loading, setLoading] = useState(true);

  const api = axios.create({ baseURL: `${BACKEND_URL}/api` });

  api.interceptors.request.use((config) => {
    const t = localStorage.getItem("roddos_token");
    if (t) config.headers.Authorization = `Bearer ${t}`;
    return config;
  });

  api.interceptors.response.use(
    (res) => res,
    (err) => {
      if (err.response?.status === 401) {
        localStorage.removeItem("roddos_token");
        setToken(null);
        setUser(null);
        window.location.href = "/login";
      }
      return Promise.reject(err);
    }
  );

  const login = useCallback(async (email: string, password: string): Promise<LoginResult> => {
    const resp = await api.post("/auth/login", { email, password });
    if (resp.data.requires_2fa) {
      return { requires_2fa: true, temp_token: resp.data.temp_token };
    }
    const { token: t, user: u } = resp.data;
    localStorage.setItem("roddos_token", t);
    setToken(t);
    setUser(u);
    return { requires_2fa: false, user: u };
  }, []); // eslint-disable-line

  const setAuth = useCallback((t: string, u: User) => {
    localStorage.setItem("roddos_token", t);
    setToken(t);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("roddos_token");
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    const fetchMe = async () => {
      if (!token) { setLoading(false); return; }
      try {
        const resp = await api.get("/auth/me");
        setUser(resp.data);
      } catch {
        localStorage.removeItem("roddos_token");
        setToken(null);
      } finally {
        setLoading(false);
      }
    };
    fetchMe();
  }, []); // eslint-disable-line

  return (
    <AuthContext.Provider value={{ user, token, login, logout, setAuth, api, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
