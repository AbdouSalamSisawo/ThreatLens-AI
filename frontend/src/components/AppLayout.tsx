/* Authenticated workspace shell - sidebar, top bar and mobile drawer.
   Rendered automatically by <Layout> for any route under /app so private
   pages keep their own navigation (never the public marketing nav). */

import { useEffect, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  ChevronDown,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  ScanSearch,
  Settings,
  Shield,
  ShieldCheck,
  X,
} from "lucide-react";
import { Logo } from "./Logo";
import { useAuth } from "../auth/AuthProvider";

const APP_NAV = [
  { to: "/app", label: "Overview", icon: LayoutDashboard, exact: true },
  { to: "/app/scanner", label: "URL Scanner", icon: ScanSearch },
  { to: "/app/history", label: "Scan History", icon: History },
  { to: "/app/model-performance", label: "Model Performance", icon: Shield },
  { to: "/app/how-it-works", label: "How It Works", icon: ShieldCheck },
  { to: "/app/settings", label: "Account Settings", icon: Settings },
];

const TITLES: Array<{ match: RegExp; title: string }> = [
  { match: /^\/app\/scanner$/, title: "URL Scanner" },
  { match: /^\/app\/history\/.+$/, title: "Scan Record" },
  { match: /^\/app\/history$/, title: "Scan History" },
  { match: /^\/app\/model-performance$/, title: "Model Performance" },
  { match: /^\/app\/how-it-works$/, title: "How It Works" },
  { match: /^\/app\/settings$/, title: "Account Settings" },
  { match: /^\/app$/, title: "Overview" },
];

function initialsFor(name: string | null | undefined, email: string | null | undefined): string {
  const base = (name || email || "?").trim();
  const parts = base.split(/[\s@._-]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return base.slice(0, 2).toUpperCase();
}

export function displayNameFallback(
  displayName: string | null | undefined,
  email: string | null | undefined,
): string {
  if (displayName && displayName.trim()) return displayName.trim();
  if (email) return email.split("@")[0];
  return "Analyst";
}

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, profile, profileLoading, signOut } = useAuth();

  useEffect(() => {
    setOpen(false);
    setMenuOpen(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);

  const title =
    TITLES.find((t) => t.match.test(location.pathname))?.title ?? "ThreatLens AI";
  const displayName = profile?.display_name ?? user?.user_metadata?.display_name ?? null;
  const email = user?.email ?? null;

  async function handleSignOut() {
    await signOut();
    navigate("/login?reason=session_expired", { replace: true });
  }

  const navItem = (item: (typeof APP_NAV)[number]) => (
    <NavLink
      key={item.to}
      to={item.to}
      end={item.exact}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
          isActive
            ? "bg-accent/12 text-accent"
            : "text-text-dim hover:bg-surface-2 hover:text-text"
        }`
      }
    >
      <item.icon size={17} aria-hidden />
      {item.label}
    </NavLink>
  );

  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <a
        href="#app-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-surface focus:px-4 focus:py-2 focus:text-accent"
      >
        Skip to main content
      </a>

      {/* Top bar */}
      <header className="sticky top-0 z-40 border-b border-border bg-bg/90 backdrop-blur">
        <div className="flex h-16 items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              className="rounded-md p-2 text-text-dim hover:bg-surface hover:text-text lg:hidden"
              aria-expanded={open}
              aria-controls="app-mobile-nav"
              aria-label={open ? "Close navigation" : "Open navigation"}
              onClick={() => setOpen((v) => !v)}
            >
              {open ? <X size={20} /> : <Menu size={20} />}
            </button>
            <Link to="/app" className="hidden sm:block" aria-label="ThreatLens AI workspace">
              <Logo compact />
            </Link>
            <span
              className="hidden h-6 w-px bg-border sm:block"
              aria-hidden
            />
            <h1 className="truncate text-sm font-semibold text-text">{title}</h1>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/app/scanner"
              className="hidden rounded-md border border-accent/40 bg-accent/10 px-4 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/20 md:inline-block"
            >
              Scan a URL
            </Link>

            <div className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((v) => !v)}
                aria-expanded={menuOpen}
                aria-haspopup="menu"
                aria-label="Account menu"
                className="flex items-center gap-2 rounded-full border border-border bg-surface p-1 pr-2.5 text-left transition-colors hover:bg-surface-2"
              >
                <span
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/15 font-mono text-xs font-semibold text-accent"
                  aria-hidden
                >
                  {initialsFor(displayName, email)}
                </span>
                <span className="hidden max-w-[140px] truncate text-xs font-medium text-text sm:block">
                  {profileLoading ? "…" : displayNameFallback(displayName, email)}
                </span>
                <ChevronDown size={14} className="text-text-dim" aria-hidden />
              </button>

              {menuOpen && (
                <div
                  role="menu"
                  aria-label="Account"
                  className="absolute right-0 top-full z-50 mt-2 w-64 rounded-xl border border-border bg-surface p-2 shadow-2xl shadow-black/40"
                >
                  <div className="border-b border-border px-3 py-2.5">
                    <p className="truncate text-sm font-medium text-text">
                      {displayNameFallback(displayName, email)}
                    </p>
                    <p className="truncate text-xs text-text-dim">{email}</p>
                  </div>
                  <Link
                    to="/app/settings"
                    role="menuitem"
                    className="mt-1 flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-text-dim hover:bg-surface-2 hover:text-text"
                  >
                    <Settings size={15} aria-hidden /> Account Settings
                  </Link>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={handleSignOut}
                    className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-danger hover:bg-danger/10"
                  >
                    <LogOut size={15} aria-hidden /> Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {open && (
          <nav
            id="app-mobile-nav"
            aria-label="Workspace"
            className="border-t border-border bg-bg lg:hidden"
          >
            <ul className="space-y-1 px-4 py-3">
              {APP_NAV.map((item) => (
                <li key={item.to}>{navItem(item)}</li>
              ))}
            </ul>
          </nav>
        )}
      </header>

      <div className="flex flex-1">
        {/* Desktop sidebar */}
        <aside className="hidden w-60 shrink-0 border-r border-border bg-bg-deep/50 lg:block">
          <nav aria-label="Workspace sections" className="sticky top-16 space-y-1 p-4">
            {APP_NAV.map((item) => navItem(item))}
            <div className="mt-6 rounded-lg border border-border bg-surface/60 p-3">
              <p className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-text-faint">
                <ShieldCheck size={12} aria-hidden /> Private workspace
              </p>
              <p className="mt-1.5 text-[11px] leading-relaxed text-text-dim">
                Scan records and statistics here belong only to{" "}
                <span className="text-text">{email}</span>.
              </p>
            </div>
          </nav>
        </aside>

        <main id="app-content" className="min-w-0 flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}
