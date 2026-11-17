/* Sign-in page - dedicated, part of the ThreatLens AI visual identity.
   Performs real Supabase Auth email/password sign-in and real Google OAuth
   (when the provider is configured in the Supabase dashboard; otherwise it
   explains exactly what still needs configuring - never fakes success). */

import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Eye, EyeOff, Info, Loader2, LogIn, ShieldCheck } from "lucide-react";
import { useAuth } from "../../auth/AuthProvider";
import { safeNextPath } from "../../auth/guards";
import {
  appUrl,
  fetchAuthSettings,
  getSupabase,
  isSupabaseConfigured,
} from "../../lib/supabase";
import { Logo } from "../../components/Logo";

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#FFC107"
        d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.5 6.1 29.5 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.1-2.6-.4-3.9z"
      />
      <path
        fill="#FF3D00"
        d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.5 6.1 29.5 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.3 0-9.7-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.5l6.2 5.2C36.9 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z"
      />
    </svg>
  );
}

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNextPath(params.get("next"));
  const { signInWithPassword } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(
    params.get("reason") === "session_expired"
      ? "Your session has expired. Please sign in again."
      : null,
  );
  const [googleConfigured, setGoogleConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchAuthSettings().then((s) => {
      if (!cancelled) setGoogleConfigured(s ? s.google : null);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    if (!email.trim() || !password) {
      setError("Enter your email address and password.");
      return;
    }
    setSubmitting(true);
    try {
      await signInWithPassword(email.trim(), password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogle() {
    setError(null);
    setNotice(null);
    if (!isSupabaseConfigured()) {
      setError(
        "Authentication is not configured in this build. Set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY (see .env.example) and rebuild.",
      );
      return;
    }
    try {
      // Real OAuth redirect to the Supabase /authorize endpoint.
      await getSupabase().auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: appUrl("/auth/callback") },
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? `Google sign-in failed: ${err.message}`
          : "Google sign-in failed.",
      );
    }
  }

  return (
    <div className="grid-bg flex min-h-screen flex-col items-center justify-center bg-bg px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <Link to="/" aria-label="ThreatLens AI home">
            <Logo />
          </Link>
          <h1 className="mt-6 text-2xl font-semibold tracking-tight text-text">
            Welcome back
          </h1>
          <p className="mt-2 max-w-sm text-sm leading-relaxed text-text-dim">
            Sign in to access your personal security workspace: your scanner,
            scan history and account settings.
          </p>
        </div>

        <div className="panel ticks p-6 sm:p-8">
          {!isSupabaseConfigured() && (
            <div className="mb-5 rounded-lg border border-warn/40 bg-warn/10 p-3 text-xs leading-relaxed text-warn">
              <span className="font-semibold">Configuration required:</span>{" "}
              Supabase credentials are missing from this build. Copy{" "}
              <code className="font-mono">.env.example</code> to{" "}
              <code className="font-mono">.env</code>, fill in the{" "}
              <code className="font-mono">VITE_SUPABASE_*</code> values and
              rebuild the frontend.
            </div>
          )}

          {error && (
            <div
              role="alert"
              className="mb-5 rounded-lg border border-danger/40 bg-danger/10 p-3 text-sm text-danger"
            >
              {error}
            </div>
          )}
          {notice && !error && (
            <div
              role="status"
              className="mb-5 rounded-lg border border-info/40 bg-info/10 p-3 text-sm text-info"
            >
              {notice}
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="login-email"
                  className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-text-dim"
                >
                  Email address
                </label>
                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="panel-inset w-full px-3.5 py-2.5 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
                />
              </div>

              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <label
                    htmlFor="login-password"
                    className="block text-xs font-semibold uppercase tracking-wider text-text-dim"
                  >
                    Password
                  </label>
                  <Link
                    to="/forgot-password"
                    className="text-xs text-accent hover:text-accent/80"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <input
                    id="login-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Your password"
                    className="panel-inset w-full px-3.5 py-2.5 pr-11 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-2 text-text-dim hover:text-text"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-bg transition-colors hover:bg-accent/85 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? (
                  <Loader2 size={16} className="animate-spin" aria-hidden />
                ) : (
                  <LogIn size={16} aria-hidden />
                )}
                {submitting ? "Signing in…" : "Sign In"}
              </button>
            </div>
          </form>

          <div className="my-5 flex items-center gap-3" aria-hidden>
            <span className="h-px flex-1 bg-border" />
            <span className="font-mono text-[10px] uppercase tracking-widest text-text-faint">
              or
            </span>
            <span className="h-px flex-1 bg-border" />
          </div>

          <button
            type="button"
            onClick={handleGoogle}
            disabled={googleConfigured === false}
            className="flex w-full items-center justify-center gap-3 rounded-lg border border-border-strong bg-surface-2 px-4 py-2.5 text-sm font-medium text-text transition-colors hover:bg-border/30 disabled:cursor-not-allowed disabled:opacity-55"
          >
            <GoogleIcon />
            Continue with Google
          </button>
          {googleConfigured === false && (
            <p className="mt-2.5 flex items-start gap-2 text-xs leading-relaxed text-text-faint">
              <Info size={13} className="mt-0.5 shrink-0" aria-hidden />
              Google sign-in is not enabled for this ThreatLens project yet. It
              must be configured once in the Supabase dashboard (Authentication
              → Providers → Google) — the application is already wired for it.
            </p>
          )}

          <p className="mt-6 text-center text-sm text-text-dim">
            New to ThreatLens AI?{" "}
            <Link
              to={`/signup${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}`}
              className="font-medium text-accent hover:text-accent/80"
            >
              Create an account
            </Link>
          </p>
        </div>

        <p className="mt-6 flex items-center justify-center gap-1.5 text-center font-mono text-[11px] text-text-faint">
          <ShieldCheck size={13} aria-hidden />
          Sessions are handled by Supabase Auth. Never share your password.
        </p>
      </div>
    </div>
  );
}
