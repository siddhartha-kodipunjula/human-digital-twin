import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { api, authStorage } from "./api";

const AuthContext = createContext(null);

function normalizeError(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((item) => item?.msg || "Invalid input").join(" | ");
  }
  return error?.message || fallback;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => authStorage.getUser());
  const [token, setToken] = useState(() => authStorage.getToken());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const bootstrap = async () => {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const { data } = await api.get("/auth/me");
        setUser(data);
        authStorage.setUser(data);
      } catch {
        authStorage.clearAll();
        setUser(null);
        setToken(null);
      } finally {
        setLoading(false);
      }
    };
    bootstrap();
  }, [token]);

  const login = async (payload) => {
    try {
      const { data } = await api.post("/auth/login", payload);
      setToken(data.access_token);
      setUser(data.user);
      authStorage.setToken(data.access_token);
      authStorage.setUser(data.user);
      return { ok: true };
    } catch (error) {
      return { ok: false, message: normalizeError(error, "Login failed.") };
    }
  };

  const signup = async (payload) => {
    try {
      const { data } = await api.post("/auth/signup", payload);
      setToken(data.access_token);
      setUser(data.user);
      authStorage.setToken(data.access_token);
      authStorage.setUser(data.user);
      return { ok: true };
    } catch (error) {
      return { ok: false, message: normalizeError(error, "Signup failed.") };
    }
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // best effort logout
    } finally {
      authStorage.clearAll();
      setToken(null);
      setUser(null);
    }
  };

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      isAuthenticated: Boolean(token && user),
      login,
      signup,
      logout,
      setUser,
    }),
    [loading, token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
