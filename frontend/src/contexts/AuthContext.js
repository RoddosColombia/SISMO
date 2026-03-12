import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem("roddos_token"));
  const [loading, setLoading] = useState(true);

  // Axios instance with auto-auth
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

  const login = useCallback(async (email, password) => {
    const resp = await api.post("/auth/login", { email, password });
    const { token: t, user: u } = resp.data;
    localStorage.setItem("roddos_token", t);
    setToken(t);
    setUser(u);
    return u;
  }, []); // eslint-disable-line

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
    <AuthContext.Provider value={{ user, token, login, logout, api, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
