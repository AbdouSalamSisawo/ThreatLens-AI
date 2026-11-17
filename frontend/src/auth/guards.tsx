/* Route guards and validated return-path helpers.

   Protected routes wait for the auth status to resolve (no private-content
   flash), then redirect unauthenticated visitors to /login while preserving
   the originally requested path. Return paths are validated against an
   internal-path rule to prevent open redirects. */

import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./AuthProvider";

/** Only same-app internal paths are accepted as post-login destinations. */
export function safeNextPath(raw: string | null | undefined): string {
  if (!raw) return "/app";
  if (!raw.startsWith("/")) return "/app";
  if (raw.startsWith("//") || raw.startsWith("/\\")) return "/app";
  if (raw.startsWith("/auth/")) return "/app";
  if (raw.length > 200) return "/app";
  return raw;
}

/** Gate for private workspace routes. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") return <AuthLoadingScreen />;

  if (status !== "authenticated") {
    const next = encodeURIComponent(
      `${location.pathname}${location.search || ""}`,
    );
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <>{children}</>;
}

/** Gate for auth pages: signed-in users do not need login/signup forms. */
export function RequireAnon({ children }: { children: ReactNode }) {
  const { status } = useAuth();

  if (status === "loading") return <AuthLoadingScreen />;

  if (status === "authenticated") {
    const params = new URLSearchParams(
      window.location.hash.split("?")[1] ?? "",
    );
    const next = safeNextPath(params.get("next"));
    return <Navigate to={next} replace />;
  }
  return <>{children}</>;
}

export function AuthLoadingScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg">
      <div className="flex flex-col items-center gap-4" role="status" aria-live="polite">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent/30 border-t-accent" />
        <p className="font-mono text-xs uppercase tracking-widest text-text-dim">
          Checking your session…
        </p>
      </div>
    </div>
  );
}
