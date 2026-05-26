import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth-context";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [formData, setFormData] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    const result = await login(formData);
    setLoading(false);

    if (!result.ok) {
      setError(result.message);
      return;
    }
    const target = location.state?.from || "/dashboard";
    navigate(target, { replace: true });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-mesh px-4">
      <div className="panel w-full max-w-md p-6">
        <h1 className="font-heading text-2xl font-bold">Welcome Back</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          Sign in to your personalized wellness digital twin.
        </p>
        {error && <div className="mt-3 rounded-lg bg-rose-500/10 p-2 text-sm text-rose-700 dark:text-rose-300">{error}</div>}
        <form onSubmit={handleSubmit} className="mt-4 space-y-3">
          <label className="block text-sm font-medium">
            Email
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData((value) => ({ ...value, email: e.target.value }))}
              required
              className="mt-1 w-full rounded-lg border border-slate-300/40 bg-white/70 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900/50"
            />
          </label>
          <label className="block text-sm font-medium">
            Password
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData((value) => ({ ...value, password: e.target.value }))}
              required
              minLength={8}
              className="mt-1 w-full rounded-lg border border-slate-300/40 bg-white/70 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900/50"
            />
          </label>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:opacity-70"
          >
            {loading ? "Signing in..." : "Login"}
          </button>
        </form>
        <p className="mt-4 text-sm text-slate-600 dark:text-slate-300">
          New here?{" "}
          <Link to="/signup" className="font-semibold text-cyan-700 dark:text-cyan-300">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
