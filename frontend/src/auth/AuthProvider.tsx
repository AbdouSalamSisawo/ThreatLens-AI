/* Central authentication state provider (Supabase Auth).

   Responsibilities:
   * Restore the session on load (loading gate prevents protected content
     from flashing before auth status is known).
   * Keep session/user/profile state in sync via onAuthStateChange.
   * Expose sign-in / sign-up / sign-out / password-recovery actions.
   * Clear ALL personal state when the signed-in account changes or signs
     out (profile, display name, cached scan data is never persisted here).
   * Attempt silent token refresh when the API reports 401.
   * Never log tokens, passwords or other sensitive session data. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { Session, User } from "@supabase/supabase-js";
import { appUrl, getSupabase, isSupabaseConfigured } from "../lib/supabase";
import {
  notifyUnauthorized,
  onUnauthorized,
  setAccessToken,
} from "./authToken";

export interface Profile {
  display_name: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  session: Session | null;
  user: User | null;
  profile: Profile | null;
  profileLoading: boolean;
  profileError: string | null;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signUpWithPassword: (
    email: string,
    password: string,
    displayName: string,
  ) => Promise<{ needsEmailConfirmation: boolean }>;
  signInWithGoogle: () => Promise<void>;
  requestPasswordReset: (email: string) => Promise<void>;
  updatePassword: (newPassword: string) => Promise<void>;
  updateDisplayName: (name: string) => Promise<Profile>;
  refreshProfile: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function friendlyAuthError(code: string | undefined, message: string): string {
  switch (code) {
    case "invalid_credentials":
    case "user_not_found":
      return "Incorrect email or password. Please try again.";
    case "email_not_confirmed":
      return "This email address has not been confirmed yet. Check your inbox for the verification link.";
    case "user_banned":
      return "This account has been disabled.";
    case "over_request_rate_limit":
    case "over_email_send_rate_limit":
      return code === "over_email_send_rate_limit"
        ? "Too many verification emails have been sent for this project. Please try again in about an hour, or sign in if your account already exists."
        : "Too many attempts. Please wait a moment before trying again.";
    case "user_already_exists":
    case "email_exists":
      return "An account with this email already exists. Try signing in instead.";
    case "weak_password":
      return "That password is too weak. Use at least 8 characters.";
    case "same_password":
      return "Choose a password different from the current one.";
    default:
      return message || "Authentication failed. Please try again.";
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const activeUserId = useRef<string | null>(null);

  const loadProfile = useCallback(async (authToken: string) => {
    setProfileLoading(true);
    setProfileError(null);
    try {
      const res = await fetch("/api/profile", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        const msg =
          body?.error?.message ?? "Profile information is unavailable right now.";
        setProfileError(msg);
        setProfile(null);
      } else {
        setProfile(body as Profile);
      }
    } catch {
      setProfileError("Could not reach the ThreatLens backend for your profile.");
      setProfile(null);
    } finally {
      setProfileLoading(false);
    }
  }, []);

  // Initial session restore + subscription to auth state changes.
  useEffect(() => {
    if (!isSupabaseConfigured()) {
      setStatus("unauthenticated");
      return;
    }
    const supabase = getSupabase();

    supabase.auth
      .getSession()
      .then(({ data }) => {
        const s = data.session;
        setSession(s);
        setUser(s?.user ?? null);
        setStatus(s ? "authenticated" : "unauthenticated");
        activeUserId.current = s?.user?.id ?? null;
        setAccessToken(s?.access_token ?? null);
      })
      .catch(() => setStatus("unauthenticated"));

    const { data: sub } = supabase.auth.onAuthStateChange((event, s) => {
      setSession(s);
      setUser(s?.user ?? null);
      setAccessToken(s?.access_token ?? null);

      const newUserId = s?.user?.id ?? null;
      if (event === "SIGNED_OUT" || (newUserId === null && event === "INITIAL_SESSION")) {
        // Full personal-state reset on logout / account switch.
        activeUserId.current = null;
        setProfile(null);
        setProfileError(null);
        setProfileLoading(false);
        setStatus("unauthenticated");
      } else if (newUserId && newUserId !== activeUserId.current) {
        // Account switched: drop cached personal data before loading anew.
        activeUserId.current = newUserId;
        setProfile(null);
        setProfileError(null);
        setStatus("authenticated");
        if (s?.access_token) void loadProfile(s.access_token);
      } else if (newUserId && status === "loading") {
        setStatus("authenticated");
        if (s?.access_token) void loadProfile(s.access_token);
      }
    });

    return () => sub.subscription.unsubscribe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadProfile]);

  // API-reported 401: try a silent refresh once; the api client retries.
  useEffect(() => {
    return onUnauthorized(() => {
      if (!isSupabaseConfigured()) return;
      void getSupabase()
        .auth.refreshSession()
        .then(({ data }) => {
          if (!data.session) setStatus("unauthenticated");
        });
    });
  }, []);

  const signInWithPassword = useCallback(async (email: string, password: string) => {
    const { error } = await getSupabase().auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw new Error(friendlyAuthError(error.code, error.message));
  }, []);

  const signUpWithPassword = useCallback(
    async (email: string, password: string, displayName: string) => {
      const { data, error } = await getSupabase().auth.signUp({
        email,
        password,
        options: {
          data: { display_name: displayName || undefined },
          emailRedirectTo: appUrl("/auth/callback"),
        },
      });
      if (error) throw new Error(friendlyAuthError(error.code, error.message));
      const needsConfirmation = !data.session && Boolean(data.user);
      return { needsEmailConfirmation: needsConfirmation };
    },
    [],
  );

  const signInWithGoogle = useCallback(async () => {
    const { error } = await getSupabase().auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: appUrl("/auth/callback") },
    });
    if (error) {
      throw new Error(
        friendlyAuthError(undefined, error.message) ||
          "Google sign-in failed. Please try again.",
      );
    }
  }, []);

  const requestPasswordReset = useCallback(async (email: string) => {
    const { error } = await getSupabase().auth.resetPasswordForEmail(email, {
      redirectTo: appUrl("/auth/callback?type=recovery"),
    });
    if (error) throw new Error(friendlyAuthError(error.code, error.message));
  }, []);

  const updatePassword = useCallback(async (newPassword: string) => {
    const { error } = await getSupabase().auth.updateUser({
      password: newPassword,
    });
    if (error) throw new Error(friendlyAuthError(error.code, error.message));
  }, []);

  const updateDisplayName = useCallback(async (name: string) => {
    const authToken = (await getSupabase().auth.getSession()).data.session
      ?.access_token;
    if (!authToken) throw new Error("Your session has expired. Please sign in again.");
    const res = await fetch("/api/profile", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ display_name: name }),
    });
    const body = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error(
        body?.error?.message ?? "Could not save your display name. Try again.",
      );
    }
    const saved = body as Profile;
    setProfile(saved);
    return saved;
  }, []);

  const refreshProfile = useCallback(async () => {
    const authToken = (await getSupabase().auth.getSession()).data.session
      ?.access_token;
    if (authToken) await loadProfile(authToken);
  }, [loadProfile]);

  const signOut = useCallback(async () => {
    try {
      await getSupabase().auth.signOut();
    } finally {
      // Personal state is cleared unconditionally, even if the network call
      // failed - the local workspace must never outlive the session.
      setAccessToken(null);
      setSession(null);
      setUser(null);
      setProfile(null);
      setProfileError(null);
      activeUserId.current = null;
      setStatus("unauthenticated");
      notifyUnauthorized();
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      session,
      user,
      profile,
      profileLoading,
      profileError,
      signInWithPassword,
      signUpWithPassword,
      signInWithGoogle,
      requestPasswordReset,
      updatePassword,
      updateDisplayName,
      refreshProfile,
      signOut,
    }),
    [
      status,
      session,
      user,
      profile,
      profileLoading,
      profileError,
      signInWithPassword,
      signUpWithPassword,
      signInWithGoogle,
      requestPasswordReset,
      updatePassword,
      updateDisplayName,
      refreshProfile,
      signOut,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
