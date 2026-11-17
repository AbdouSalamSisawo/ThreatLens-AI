/* Set-new-password page, reached only through a valid Supabase recovery
   session (the recovery email link establishes one). */

import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Loader2, ShieldCheck } from "lucide-react";
import { useAuth } from "../../auth/AuthProvider";
import { Logo } from "../../components/Logo";

const PASSWORD_MIN = 8;

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const { updatePassword, signOut } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < PASSWORD_MIN)
      return setError(`Password must be at least ${PASSWORD_MIN} characters long.`);
    if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password))
      return setError("Password must contain at least one letter and one number.");
    if (password !== confirm) return setError("Passwords do not match.");

    setSubmitting(true);
    try {
      await updatePassword(password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update the password.");
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
          {done ? (
            <div className="text-center">
              <ShieldCheck className="mx-auto text-ok" size={40} aria-hidden />
              <h1 className="mt-4 text-xl font-semibold text-text">
                Password updated
              </h1>
              <p className="mt-3 text-sm leading-relaxed text-text-dim">
                Your password has been changed. Use it to sign in from now on.
              </p>
              <button
                type="button"
                onClick={async () => {
                  await signOut();
                  navigate("/login", { replace: true });
                }}
                className="mt-6 inline-block rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-bg hover:bg-accent/85"
              >
                Continue to sign in
              </button>
            </div>
          ) : (
            <>
              <h1 className="text-xl font-semibold tracking-tight text-text">
                Set a new password
              </h1>
              <p className="mt-2 text-sm leading-relaxed text-text-dim">
                Choose a strong new password for your ThreatLens AI account.
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
                <div className="space-y-4">
                  <div className="relative">
                    <label
                      htmlFor="new-password"
                      className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-text-dim"
                    >
                      New password
                    </label>
                    <input
                      id="new-password"
                      type={show ? "text" : "password"}
                      autoComplete="new-password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder={`At least ${PASSWORD_MIN} characters, 1 letter + 1 number`}
                      className="panel-inset w-full px-3.5 py-2.5 pr-11 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => setShow((v) => !v)}
                      aria-label={show ? "Hide password" : "Show password"}
                      className="absolute right-1.5 top-[calc(50%+10px)] -translate-y-1/2 rounded p-2 text-text-dim hover:text-text"
                    >
                      {show ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  <div>
                    <label
                      htmlFor="confirm-password"
                      className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-text-dim"
                    >
                      Confirm new password
                    </label>
                    <input
                      id="confirm-password"
                      type={show ? "text" : "password"}
                      autoComplete="new-password"
                      required
                      value={confirm}
                      onChange={(e) => setConfirm(e.target.value)}
                      placeholder="Repeat your new password"
                      className="panel-inset w-full px-3.5 py-2.5 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-bg transition-colors hover:bg-accent/85 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {submitting && (
                      <Loader2 size={16} className="animate-spin" aria-hidden />
                    )}
                    {submitting ? "Updating…" : "Update password"}
                  </button>
                </div>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
