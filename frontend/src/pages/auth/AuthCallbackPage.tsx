/* Auth callback route - completes PKCE OAuth (Google) and email-link flows
   (confirmation, recovery) by exchanging the code for a session, then routes
   to the validated destination. Handles cancelled logins and provider errors
   explicitly instead of hanging. */

import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, Loader2 } from "lucide-react";
import { getSupabase, isSupabaseConfigured } from "../../lib/supabase";
import { safeNextPath } from "../../auth/guards";
import { useAuth } from "../../auth/AuthProvider";
import { Logo } from "../../components/Logo";

type Outcome =
  | { kind: "working" }
  | { kind: "error"; message: string }
  | { kind: "recovery" };

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { status } = useAuth();
  const [outcome, setOutcome] = useState<Outcome>({ kind: "working" });
  const exchanged = useRef(false);

  useEffect(() => {
    if (exchanged.current) return;
    exchanged.current = true;

    const type = params.get("type");
    const next = safeNextPath(params.get("next"));
    const oauthError = params.get("error");
    const oauthErrorDescription = params.get("error_description");

    // Google-side cancellations / provider errors arrive as query params.
    if (oauthError) {
      setOutcome({
        kind: "error",
        message:
          oauthError === "access_denied"
            ? "The Google sign-in was cancelled. No account was accessed — you can try again."
            : `Google sign-in failed: ${oauthErrorDescription || oauthError}`,
      });
      return;
    }

    if (!isSupabaseConfigured()) {
      setOutcome({
        kind: "error",
        message:
          "Authentication is not configured in this build (missing VITE_SUPABASE_* environment variables).",
      });
      return;
    }

    const supabase = getSupabase();

    async function complete() {
      try {
        const url = window.location.href;
        const hasCode = new URL(url).searchParams.has("code");

        if (hasCode) {
          // PKCE: exchange the one-time code. With detectSessionInUrl the
          // client may already have consumed it - double exchange errors are
          // tolerated as long as a session exists afterwards.
          const { error } = await supabase.auth.exchangeCodeForSession(url);
          if (error && !error.message.toLowerCase().includes("already")) {
            const { data } = await supabase.auth.getSession();
            if (!data.session) throw error;
          }
        }

        const { data } = await supabase.auth.getSession();
        if (!data.session) {
          setOutcome({
            kind: "error",
            message:
              "No valid session was established. The link may have expired or already been used — request a new one.",
          });
          return;
        }

        if (type === "recovery") {
          setOutcome({ kind: "recovery" });
          navigate("/auth/reset-password", { replace: true });
          return;
        }

        navigate(next, { replace: true });
      } catch (err) {
        setOutcome({
          kind: "error",
          message:
            err instanceof Error
              ? `Could not complete sign-in: ${err.message}`
              : "Could not complete sign-in.",
        });
      }
    }

    void complete();
  }, [navigate, params]);

  // Fallback: if the session appeared via detectSessionInUrl while this page
  // is still mounted, move on.
  useEffect(() => {
    if (status === "authenticated" && outcome.kind === "working") {
      const t = setTimeout(() => {
        if (params.get("type") === "recovery") {
          navigate("/auth/reset-password", { replace: true });
        } else {
          navigate(safeNextPath(params.get("next")), { replace: true });
        }
      }, 600);
      return () => clearTimeout(t);
    }
  }, [status, outcome, navigate, params]);

  return (
    <div className="grid-bg flex min-h-screen flex-col items-center justify-center bg-bg px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>
        <div className="panel ticks p-8 text-center">
          {outcome.kind === "working" && (
            <>
              <Loader2
                size={32}
                className="mx-auto animate-spin text-accent"
                aria-hidden
              />
              <p
                className="mt-4 font-mono text-xs uppercase tracking-widest text-text-dim"
                role="status"
                aria-live="polite"
              >
                Completing sign-in…
              </p>
            </>
          )}
          {outcome.kind === "recovery" && (
            <p
              className="font-mono text-xs uppercase tracking-widest text-text-dim"
              role="status"
            >
              Opening password reset…
            </p>
          )}
          {outcome.kind === "error" && (
            <>
              <AlertTriangle size={32} className="mx-auto text-warn" aria-hidden />
              <h1 className="mt-4 text-lg font-semibold text-text">
                Sign-in could not be completed
              </h1>
              <p className="mt-3 text-sm leading-relaxed text-text-dim">
                {outcome.message}
              </p>
              <div className="mt-6 flex items-center justify-center gap-3">
                <Link
                  to="/login"
                  className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-bg hover:bg-accent/85"
                >
                  Back to sign in
                </Link>
                <Link
                  to="/"
                  className="rounded-lg border border-border-strong bg-surface-2 px-5 py-2.5 text-sm font-medium text-text hover:bg-border/30"
                >
                  Go to homepage
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
