/* Registration page - real Supabase Auth sign-up with a password policy,
   duplicate-email handling and an honest email-confirmation screen. */

import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  CheckCircle2,
  Eye,
  EyeOff,
  Info,
  Loader2,
  MailCheck,
  ShieldCheck,
  UserPlus,
} from "lucide-react";
import { useAuth } from "../../auth/AuthProvider";
import { safeNextPath } from "../../auth/guards";
import {
  appUrl,
  fetchAuthSettings,
  getSupabase,
  isSupabaseConfigured,
} from "../../lib/supabase";
import { Logo } from "../../components/Logo";

const PASSWORD_MIN = 8;

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

function validate(email: string, password: string, confirm: string, name: string): string | null {
  if (!name.trim()) return "Enter a display name (you can change it later).";
  if (name.trim().length > 60) return "Display name must be 60 characters or fewer.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))
    return "Enter a valid email address.";
  if (password.length < PASSWORD_MIN)
    return `Password must be at least ${PASSWORD_MIN} characters long.`;
  if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password))
    return "Password must contain at least one letter and one number.";
  if (password !== confirm) return "Passwords do not match.";
  return null;
}

export function SignupPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNextPath(params.get("next"));
  const { signUpWithPassword } = useAuth();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmSent, setConfirmSent] = useState(false);
  const [confirmedEmail, setConfirmedEmail] = useState("");
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
    const problem = validate(email, password, confirm, displayName);
    if (problem) {
      setError(problem);
      return;
    }
    setSubmitting(true);
    try {
      const result = await signUpWithPassword(
        email.trim(),
        password,
        displayName.trim(),
      );
      if (result.needsEmailConfirmation) {
        setConfirmedEmail(email.trim());
        setConfirmSent(true);
      } else {
        navigate(next, { replace: true });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogle() {
    setError(null);
    if (!isSupabaseConfigured()) {
      setError(
        "Authentication is not configured in this build. Set VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY (see .env.example) and rebuild.",
      );
      return;
    }
    try {
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

  if (confirmSent) {
    return (
      <div className="grid-bg flex min-h-screen flex-col items-center justify-center bg-bg px-4 py-10">
        <div className="w-full max-w-md">
          <div className="mb-8 flex justify-center">
            <Link to="/" aria-label="ThreatLens AI home">
              <Logo />
            </Link>
          </div>
          <div className="panel ticks p-8 text-center">
            <MailCheck className="mx-auto text-accent" size={40} aria-hidden />
            <h1 className="mt-4 text-xl font-semibold text-text">
              Confirm your email address
            </h1>
            <p className="mt-3 text-sm leading-relaxed text-text-dim">
              We sent a confirmation link to{" "}
              <span className="font-medium text-text">{confirmedEmail}</span>.
              Open that link to activate your account, then sign in below.
            </p>
            <p className="mt-3 text-xs leading-relaxed text-text-faint">
              The link expires after a while. If it does not arrive, check your
              spam folder or ask the project administrator to review the
              Supabase Auth email settings.
            </p>
            <Link
              to={`/login${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}`}
              className="mt-6 inline-block rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-bg hover:bg-accent/85"
            >
              Back to sign in
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="grid-bg flex min-h-screen flex-col items-center justify-center bg-bg px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center text-center">
          <Link to="/" aria-label="ThreatLens AI home">
            <Logo />
          </Link>
          <h1 className="mt-6 text-2xl font-semibold tracking-tight text-text">
            Create your account
          </h1>
          <p className="mt-2 max-w-sm text-sm leading-relaxed text-text-dim">
            Set up your personal security workspace. Your scans and history
            stay private to your account.
          </p>
        </div>

        <div className="panel ticks p-6 sm:p-8">
          {!isSupabaseConfigured() && (
            <div className="mb-5 rounded-lg border border-warn/40 bg-warn/10 p-3 text-xs leading-relaxed text-warn">
              <span className="font-semibold">Configuration required:</span>{" "}
              Supabase credentials are missing from this build (see{" "}
              <code className="font-mono">.env.example</code>).
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

          <form onSubmit={handleSubmit} noValidate>
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="signup-name"
                  className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-text-dim"
                >
                  Display name
                </label>
                <input
                  id="signup-name"
                  type="text"
                  autoComplete="name"
                  maxLength={60}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="How should we greet you?"
                  className="panel-inset w-full px-3.5 py-2.5 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
                />
              </div>

              <div>
                <label
                  htmlFor="signup-email"
                  className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-text-dim"
                >
                  Email address
                </label>
                <input
                  id="signup-email"
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
                <label
                  htmlFor="signup-password"
                  className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-text-dim"
                >
                  Password
                </label>
                <div className="relative">
                  <input
                    id="signup-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={`At least ${PASSWORD_MIN} characters, 1 letter + 1 number`}
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

              <div>
                <label
                  htmlFor="signup-confirm"
                  className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-text-dim"
                >
                  Confirm password
                </label>
                <input
                  id="signup-confirm"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  required
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Repeat your password"
                  className="panel-inset w-full px-3.5 py-2.5 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
                />
                {confirm.length > 0 && (
                  <p
                    className={`mt-1.5 flex items-center gap-1.5 text-xs ${
                      confirm === password ? "text-ok" : "text-warn"
                    }`}
                  >
                    {confirm === password ? (
                      <CheckCircle2 size={13} aria-hidden />
                    ) : null}
                    {confirm === password
                      ? "Passwords match"
                      : "Passwords do not match yet"}
                  </p>
                )}
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-bg transition-colors hover:bg-accent/85 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? (
                  <Loader2 size={16} className="animate-spin" aria-hidden />
                ) : (
                  <UserPlus size={16} aria-hidden />
                )}
                {submitting ? "Creating account…" : "Create Account"}
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
              Google sign-in is not enabled for this ThreatLens project yet —
              it must be configured in the Supabase dashboard (Authentication
              → Providers → Google).
            </p>
          )}

          <p className="mt-6 text-center text-sm text-text-dim">
            Already have an account?{" "}
            <Link
              to={`/login${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}`}
              className="font-medium text-accent hover:text-accent/80"
            >
              Sign in
            </Link>
          </p>
        </div>

        <p className="mt-6 flex items-center justify-center gap-1.5 text-center font-mono text-[11px] text-text-faint">
          <ShieldCheck size={13} aria-hidden />
          Passwords are handled exclusively by Supabase Auth — never stored in
          this application.
        </p>
      </div>
    </div>
  );
}
