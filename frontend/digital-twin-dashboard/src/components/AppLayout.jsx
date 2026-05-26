import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../auth-context";

function navClass({ isActive }) {
  return `rounded-lg px-3 py-2 text-sm font-semibold transition ${
    isActive
      ? "bg-slate-900 text-white"
      : "text-slate-700 hover:bg-slate-900/10 dark:text-slate-200 dark:hover:bg-white/10"
  }`;
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-mesh">
      <header className="border-b border-slate-300/20 bg-white/80 backdrop-blur dark:bg-slate-900/80">
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 md:px-6">
          <Link to="/dashboard" className="font-heading text-xl font-bold text-slate-900 dark:text-slate-100">
            Human Digital Twin
          </Link>
          <nav className="flex items-center gap-2">
            <NavLink to="/dashboard" className={navClass}>
              Dashboard
            </NavLink>
            <NavLink to="/profile" className={navClass}>
              Profile
            </NavLink>
          </nav>
          <div className="flex items-center gap-2">
            <span className="hidden rounded-md bg-slate-900/5 px-3 py-1 text-xs md:block dark:bg-white/10">
              {user?.name || "User"}
            </span>
            <button
              onClick={handleLogout}
              className="rounded-lg border border-slate-300/40 px-3 py-2 text-sm font-semibold hover:bg-slate-900/10 dark:border-slate-700 dark:hover:bg-white/10"
            >
              Logout
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl px-4 py-6 md:px-6">
        <Outlet />
      </main>
    </div>
  );
}
