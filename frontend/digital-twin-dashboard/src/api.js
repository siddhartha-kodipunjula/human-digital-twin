import axios from "axios";

const browserHost = typeof window !== "undefined" ? window.location.hostname : "127.0.0.1";
const localHost = browserHost === "localhost" || browserHost === "127.0.0.1" ? browserHost : "127.0.0.1";
const baseURL = import.meta.env.VITE_API_BASE_URL || `http://${localHost}:8000/api/v1`;

const TOKEN_KEY = "digital_twin_access_token";
const USER_KEY = "digital_twin_user";

export const authStorage = {
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },
  setToken(token) {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    }
  },
  clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  },
  getUser() {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  },
  setUser(user) {
    if (user) {
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    }
  },
  clearUser() {
    localStorage.removeItem(USER_KEY);
  },
  clearAll() {
    this.clearToken();
    this.clearUser();
  },
};

export const api = axios.create({
  baseURL,
  timeout: 60000,
});

api.interceptors.request.use((config) => {
  const token = authStorage.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
