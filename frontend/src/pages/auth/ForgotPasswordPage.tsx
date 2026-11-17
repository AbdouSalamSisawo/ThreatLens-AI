/* Forgot-password page - requests a real password-reset email from Supabase
   Auth. Never reveals whether an email address has an account; provider
   errors are surfaced honestly without inventing a "sent" state. */

import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { KeyRound, Loader2, MailCheck } from "lucide-react";
import { useAuth } from "../../auth/AuthProvider";
import { Logo } from "../../components/Logo";

export function ForgotPasswordPage() {
  const { requestPasswordReset } = useAuth();
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("Enter a valid email address.");
      return;
    }
    setSubmitting(true);
    try {
      await requestPasswordReset(email.trim());
      setSent(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not request a reset email. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid-bg flex min-h-screen flex-col items-center justify-center bg-bg px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Link to="/" aria-label="ThreatLens AI home">
            <Logo />
          </Link>
        </div>

        <div className="panel ticks p-6 sm:p-8">
          {sent ? (
            <div className="text-center">
              <MailCheck className="mx-auto text-accent" size={40} aria-hidden />
              <h1 className="mt-4 text-xl font-semibold text-text">
                Check your inbox
              </h1>
              <p className="mt-3 text-sm leading-relaxed text-text-dim">
                If an account exists for{" "}
                <span className="font-medium text-text">{email}</span>, a
                password-reset link is on its way. Open the link to set a new
                password — it returns you to ThreatLens AI.
              </p>
              <p className="mt-3 text-xs text-text-faint">
                For privacy reasons we do not reveal whether an email address
                is registered.
              </p>
              <Link
                to="/login"
                className="mt-6 inline-block rounded-lg border border-border-strong bg-surface-2 px-5 py-2.5 text-sm font-medium text-text hover:bg-border/30"
              >
                Back to sign in
              </Link>
            </div>
          ) : (
            <>
              <h1 className="text-xl font-semibold tracking-tight text-text">
                Reset your password
              </h1>
              <p className="mt-2 text-sm leading-relaxed text-text-dim">
                Enter the email address on your account and we will send a
                secure reset link.
              </p>

              {error && (
                <div
                  role="alert"
                  className="mt-5 rounded-lg border border-danger/40 bg-danger/10 p-3 text-sm text-danger"
                >
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} noValidate className="mt-5">
                <label
                  htmlFor="reset-email"
                  className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-text-dim"
                >
                  Email address
                </label>
                <input
                  id="reset-email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="panel-inset w-full px-3.5 py-2.5 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={submitting}
                  className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-bg transition-colors hover:bg-accent/85 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? (
                    <Loader2 size={16} className="animate-spin" aria-hidden />
                  ) : (
                    <KeyRound size={16} aria-hidden />
                  )}
                  {submitting ? "Sending…" : "Send reset link"}
                </button>
              </form>

              <p className="mt-6 text-center text-sm text-text-dim">
                Remembered it?{" "}
                <Link to="/login" className="font-medium text-accent hover:text-accent/80">
                  Sign in
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
