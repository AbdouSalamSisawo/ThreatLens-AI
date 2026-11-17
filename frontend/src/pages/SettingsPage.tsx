/* Account settings - profile, security and session controls.

   Honesty rules applied here:
   * Only controls that actually work are rendered (no fake theme toggles,
     no non-functional avatar upload, no pretend account deletion).
   * Password change for email accounts uses the real Supabase recovery
     email flow; Google-only accounts see an explanatory note instead.
   * Account deletion requires privileged server-side operations that this
     deployment deliberately does not hold, so it is documented rather than
     presented as a broken button. */

import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  AtSign,
  CalendarDays,
  CheckCircle2,
  Info,
  KeyRound,
  Loader2,
  LogOut,
  Save,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useAuth } from "../auth/AuthProvider";
import { displayNameFallback } from "../components/AppLayout";

function providerLabel(user: { app_metadata?: Record<string, unknown> } | null): string {
  const meta = user?.app_metadata ?? {};
  const providers = (meta.providers as string[] | undefined) ?? [];
  if (providers.includes("google")) return "Google";
  if (providers.includes("email")) return "Email & password";
  return (meta.provider as string) ?? "Unknown";
}

function emailVerified(user: { email_confirmed_at?: string | null } | null): boolean {
  return Boolean(user?.email_confirmed_at);
}

export function SettingsPage() {
  const { user, profile, profileLoading, profileError, updateDisplayName, updatePassword, signOut } =
    useAuth();

  const [name, setName] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [nameMessage, setNameMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const displayName = profile?.display_name ?? user?.user_metadata?.display_name ?? null;
  const email = user?.email ?? null;
  const isGoogleOnly = providerLabel(user) === "Google";
  const createdAt = user?.created_at
    ? new Date(user.created_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : null;

  useEffect(() => {
    setName(displayName ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.display_name, user?.id]);

  async function handleSaveName(e: FormEvent) {
    e.preventDefault();
    setNameMessage(null);
    const trimmed = name.trim();
    if (!trimmed) {
      setNameMessage({ ok: false, text: "Display name cannot be empty." });
      return;
    }
    setSavingName(true);
    try {
      await updateDisplayName(trimmed);
      setNameMessage({ ok: true, text: "Display name saved." });
    } catch (err) {
      setNameMessage({
        ok: false,
        text: err instanceof Error ? err.message : "Could not save your display name.",
      });
    } finally {
      setSavingName(false);
    }
  }

  async function handlePasswordChange(e: FormEvent) {
    e.preventDefault();
    setPasswordMessage(null);
    if (newPassword.length < 8)
      return setPasswordMessage({ ok: false, text: "Password must be at least 8 characters." });
    if (!/[A-Za-z]/.test(newPassword) || !/[0-9]/.test(newPassword))
      return setPasswordMessage({
        ok: false,
        text: "Password must contain at least one letter and one number.",
      });
    if (newPassword !== confirmPassword)
      return setPasswordMessage({ ok: false, text: "Passwords do not match." });

    setSavingPassword(true);
    try {
      await updatePassword(newPassword);
      setPasswordMessage({ ok: true, text: "Password updated." });
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setPasswordMessage({
        ok: false,
        text: err instanceof Error ? err.message : "Could not update the password.",
      });
    } finally {
      setSavingPassword(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <h2 className="text-xl font-semibold tracking-tight text-text">Account Settings</h2>
      <p className="mt-1 text-sm text-text-dim">
        Manage your profile and sign-in security. Changes apply only to your account.
      </p>

      {/* Profile */}
      <section aria-labelledby="profile-heading" className="panel mt-6 p-6">
        <div className="flex items-center gap-4">
          <span
            className="flex h-14 w-14 items-center justify-center rounded-full bg-accent/15 font-mono text-base font-semibold text-accent"
            aria-hidden
          >
            {(displayNameFallback(displayName, email).slice(0, 2)).toUpperCase()}
          </span>
          <div className="min-w-0">
            <h3 id="profile-heading" className="text-base font-semibold text-text">
              Profile
            </h3>
            <p className="truncate text-sm text-text-dim">
              {profileLoading ? "Loading profile…" : displayNameFallback(displayName, email)}
            </p>
          </div>
        </div>

        {profileError && (
          <div className="mt-4 rounded-lg border border-warn/40 bg-warn/10 p-3 text-xs leading-relaxed text-warn">
            <span className="font-semibold">Profile storage:</span> {profileError} If
            this mentions a migration, the Supabase SQL migration (see the
            repository <code className="font-mono">supabase/migrations/</code>{" "}
            folder) still needs to be applied by the project owner.
          </div>
        )}

        <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2">
          <div className="flex items-start gap-2.5">
            <AtSign size={16} className="mt-0.5 text-text-faint" aria-hidden />
            <div className="min-w-0">
              <dt className="text-xs uppercase tracking-wider text-text-faint">Email</dt>
              <dd className="truncate text-text">{email}</dd>
            </div>
          </div>
          <div className="flex items-start gap-2.5">
            <ShieldCheck size={16} className="mt-0.5 text-text-faint" aria-hidden />
            <div>
              <dt className="text-xs uppercase tracking-wider text-text-faint">
                Sign-in method
              </dt>
              <dd className="text-text">{providerLabel(user)}</dd>
            </div>
          </div>
          <div className="flex items-start gap-2.5">
            <CalendarDays size={16} className="mt-0.5 text-text-faint" aria-hidden />
            <div>
              <dt className="text-xs uppercase tracking-wider text-text-faint">
                Member since
              </dt>
              <dd className="text-text">{createdAt ?? "Not available"}</dd>
            </div>
          </div>
          <div className="flex items-start gap-2.5">
            <CheckCircle2
              size={16}
              className={`mt-0.5 ${emailVerified(user) ? "text-ok" : "text-warn"}`}
              aria-hidden
            />
            <div>
              <dt className="text-xs uppercase tracking-wider text-text-faint">
                Email status
              </dt>
              <dd className="text-text">
                {emailVerified(user) ? "Verified" : "Not verified yet"}
              </dd>
            </div>
          </div>
        </dl>

        <form onSubmit={handleSaveName} className="mt-6 border-t border-border pt-5">
          <label
            htmlFor="settings-name"
            className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-dim"
          >
            <UserRound size={13} aria-hidden /> Display name
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              id="settings-name"
              type="text"
              maxLength={60}
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="panel-inset w-full px-3.5 py-2.5 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
            />
            <button
              type="submit"
              disabled={savingName || name.trim() === (displayName ?? "")}
              className="flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-bg transition-colors hover:bg-accent/85 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {savingName ? (
                <Loader2 size={15} className="animate-spin" aria-hidden />
              ) : (
                <Save size={15} aria-hidden />
              )}
              Save
            </button>
          </div>
          {nameMessage && (
            <p
              role="status"
              className={`mt-2.5 text-sm ${nameMessage.ok ? "text-ok" : "text-danger"}`}
            >
              {nameMessage.text}
            </p>
          )}
        </form>
      </section>

      {/* Security */}
      <section aria-labelledby="security-heading" className="panel mt-6 p-6">
        <h3 id="security-heading" className="text-base font-semibold text-text">
          Security
        </h3>
        <p className="mt-1 text-sm text-text-dim">
          {isGoogleOnly
            ? "You sign in with Google. Password management is handled by your Google account — ThreatLens AI never stores a password for this account."
            : "Change your password below. For your security the new password is verified by Supabase Auth."}
        </p>

        {!isGoogleOnly && (
          <form onSubmit={handlePasswordChange} className="mt-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="settings-new-password"
                  className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-text-dim"
                >
                  New password
                </label>
                <input
                  id="settings-new-password"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  className="panel-inset w-full px-3.5 py-2.5 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
                />
              </div>
              <div>
                <label
                  htmlFor="settings-confirm-password"
                  className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-text-dim"
                >
                  Confirm new password
                </label>
                <input
                  id="settings-confirm-password"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat new password"
                  className="panel-inset w-full px-3.5 py-2.5 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={savingPassword}
              className="mt-4 flex items-center gap-2 rounded-lg border border-accent/40 bg-accent/10 px-4 py-2.5 text-sm font-medium text-accent transition-colors hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {savingPassword ? (
                <Loader2 size={15} className="animate-spin" aria-hidden />
              ) : (
                <KeyRound size={15} aria-hidden />
              )}
              {savingPassword ? "Updating…" : "Update password"}
            </button>
            {passwordMessage && (
              <p
                role="status"
                className={`mt-2.5 text-sm ${passwordMessage.ok ? "text-ok" : "text-danger"}`}
              >
                {passwordMessage.text}
              </p>
            )}
          </form>
        )}

        <div className="mt-6 border-t border-border pt-5">
          <h4 className="text-sm font-semibold text-text">Sign out of this device</h4>
          <p className="mt-1 text-xs leading-relaxed text-text-dim">
            Signing out clears your session and all cached personal data in this
            browser (profile, scan results, history filters).
          </p>
          <button
            type="button"
            onClick={() => void signOut()}
            className="mt-3 flex items-center gap-2 rounded-lg border border-danger/40 bg-danger/10 px-4 py-2.5 text-sm font-medium text-danger transition-colors hover:bg-danger/20"
          >
            <LogOut size={15} aria-hidden /> Sign out
          </button>
        </div>
      </section>

      {/* Account deletion - documented limitation, no fake button */}
      <section aria-labelledby="deletion-heading" className="panel mt-6 p-6">
        <h3 id="deletion-heading" className="text-base font-semibold text-text">
          Deleting your account
        </h3>
        <p className="mt-2 flex items-start gap-2 text-sm leading-relaxed text-text-dim">
          <Info size={15} className="mt-0.5 shrink-0 text-info" aria-hidden />
          Account deletion requires a privileged server-side operation that this
          prototype deliberately does not perform (the backend holds no
          service-role key, by least-privilege design). To have your account and
          scan records removed, contact the project team, who will perform the
          deletion through the Supabase dashboard. Your scan records can be
          cleared at any time yourself via{" "}
          <Link to="/app/history" className="text-info hover:underline">
            Scan History → Clear all
          </Link>
          .
        </p>
      </section>
    </div>
  );
}
