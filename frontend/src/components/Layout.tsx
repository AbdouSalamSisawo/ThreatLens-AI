import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { Logo } from "./Logo";
import { AppLayout } from "./AppLayout";
import { useAuth } from "../auth/AuthProvider";

const NAV = [
  { to: "/", label: "Home" },
  { to: "/how-it-works", label: "How It Works" },
  { to: "/model-performance", label: "Model Performance" },
  { to: "/security-privacy", label: "Security & Privacy" },
  { to: "/about", label: "About" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  // Private workspace routes get the dedicated application shell.
  if (location.pathname.startsWith("/app")) {
    return <AppLayout>{children}</AppLayout>;
  }
  return <PublicLayout>{children}</PublicLayout>;
}

function PublicLayout({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const { status } = useAuth();

  useEffect(() => {
    setOpen(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);

  const authed = status === "authenticated";

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-surface focus:px-4 focus:py-2 focus:text-accent"
      >
        Skip to main content
      </a>

      <header className="sticky top-0 z-40 border-b border-border bg-bg/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <Link to="/" aria-label="ThreatLens AI home">
            <Logo compact />
          </Link>

          <nav aria-label="Primary" className="hidden items-center gap-1 lg:flex">
            {NAV.slice(1).map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-md px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? "bg-surface-2 text-accent"
                      : "text-text-dim hover:bg-surface hover:text-text"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-2.5">
            {authed ? (
              <Link
                to="/app"
                className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg transition-colors hover:bg-accent/85"
              >
                Open workspace
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="rounded-md px-3 py-2 text-sm text-text-dim transition-colors hover:bg-surface hover:text-text"
                >
                  Sign in
                </Link>
                <Link
                  to="/app/scanner"
                  className="hidden rounded-md border border-accent/40 bg-accent/10 px-4 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/20 sm:inline-block"
                >
                  Get Started
                </Link>
              </>
            )}
            <button
              type="button"
              className="rounded-md p-2 text-text-dim hover:bg-surface hover:text-text lg:hidden"
              aria-expanded={open}
              aria-controls="mobile-nav"
              aria-label={open ? "Close menu" : "Open menu"}
              onClick={() => setOpen((v) => !v)}
            >
              {open ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {open && (
          <nav
            id="mobile-nav"
            aria-label="Mobile"
            className="border-t border-border bg-bg lg:hidden"
          >
            <ul className="mx-auto max-w-6xl px-4 py-2 sm:px-6">
              {NAV.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      `block rounded-md px-3 py-2.5 text-sm ${
                        isActive
                          ? "bg-surface-2 text-accent"
                          : "text-text-dim hover:bg-surface hover:text-text"
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}
              <li>
                <Link
                  to={authed ? "/app" : "/app/scanner"}
                  className="mt-2 block rounded-md bg-accent px-3 py-2.5 text-center text-sm font-semibold text-bg"
                >
                  {authed ? "Open workspace" : "Get Started"}
                </Link>
              </li>
              {!authed && (
                <li>
                  <Link
                    to="/login"
                    className="mt-2 block rounded-md border border-border-strong bg-surface-2 px-3 py-2.5 text-center text-sm text-text"
                  >
                    Sign in
                  </Link>
                </li>
              )}
            </ul>
          </nav>
        )}
      </header>

      <main id="main-content" className="flex-1">
        {children}
      </main>

      <footer className="mt-auto border-t border-border bg-bg-deep">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:px-6 md:grid-cols-4">
          <div className="md:col-span-2">
            <Logo />
            <p className="mt-4 max-w-md text-sm leading-relaxed text-text-dim">
              A student-built cybersecurity prototype from the School of
              Computing &amp; Informatics, Albukhary International University,
              developed for the MMC Upstart 2026 Catalyst competition. It
              screens URLs with an explainable machine-learning model — it is
              an assistive tool, not a definitive security verdict.
            </p>
          </div>
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-faint">
              Product
            </h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li><Link className="text-text-dim hover:text-accent" to="/how-it-works">How It Works</Link></li>
              <li><Link className="text-text-dim hover:text-accent" to="/model-performance">Model Performance</Link></li>
              <li>
                <Link className="text-text-dim hover:text-accent" to="/app/scanner">
                  URL Scanner (account required)
                </Link>
              </li>
              <li><Link className="text-text-dim hover:text-accent" to="/signup">Create an account</Link></li>
            </ul>
          </div>
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-faint">
              Transparency
            </h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li><Link className="text-text-dim hover:text-accent" to="/security-privacy">Security &amp; Privacy</Link></li>
              <li><Link className="text-text-dim hover:text-accent" to="/about">About the Project</Link></li>
              <li>
                <a
                  className="text-text-dim hover:text-accent"
                  href="/api/docs"
                  target="_blank"
                  rel="noreferrer"
                >
                  API Documentation
                </a>
              </li>
            </ul>
          </div>
        </div>
        <div className="border-t border-border">
          <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-4 text-xs text-text-faint sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <p>
              ThreatLens AI — student prototype. No institutional endorsement
              implied. Not affiliated with MMC or AIU officially.
            </p>
            <p className="font-mono">
              Limitations apply — see Security &amp; Privacy. Never open
              suspicious links to “check” them.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
