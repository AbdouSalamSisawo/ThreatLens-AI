/* Supabase browser client (publishable key only - safe for public bundles).

   The publishable key is designed to live in client-side code; no privileged
   credential may ever be imported here. Configuration comes from Vite env
   vars (VITE_SUPABASE_URL / VITE_SUPABASE_PUBLISHABLE_KEY) and missing
   configuration raises an explicit, actionable error instead of silently
   producing a broken auth experience. */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const SUPABASE_PUBLISHABLE_KEY = import.meta.env
  .VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined;

export class SupabaseConfigError extends Error {
  constructor() {
    super(
      "Supabase is not configured. Set VITE_SUPABASE_URL and " +
        "VITE_SUPABASE_PUBLISHABLE_KEY in threatlens/frontend/.env " +
        "(see .env.example), then rebuild the frontend.",
    );
    this.name = "SupabaseConfigError";
  }
}

let client: SupabaseClient | null = null;

export function isSupabaseConfigured(): boolean {
  return Boolean(SUPABASE_URL && SUPABASE_PUBLISHABLE_KEY);
}

export function getSupabase(): SupabaseClient {
  if (!client) {
    if (!isSupabaseConfigured()) throw new SupabaseConfigError();
    client = createClient(SUPABASE_URL!, SUPABASE_PUBLISHABLE_KEY!, {
      auth: {
        // PKCE flow: required for the /auth/callback route (OAuth + email links).
        flowType: "pkce",
        detectSessionInUrl: true,
        persistSession: true,
        autoRefreshToken: true,
      },
    });
  }
  return client;
}

/** Absolute URL for an in-app hash route (used for email/OAuth redirects). */
export function appUrl(hashPath: string): string {
  const base = window.location.href.split("#")[0];
  const path = hashPath.startsWith("/") ? hashPath : `/${hashPath}`;
  return `${base}#${path}`;
}

export interface AuthProviderSettings {
  google: boolean;
  email: boolean;
}

/** Public auth settings for this project (which providers are enabled). */
export async function fetchAuthSettings(): Promise<AuthProviderSettings | null> {
  if (!isSupabaseConfigured()) return null;
  try {
    const res = await fetch(`${SUPABASE_URL}/auth/v1/settings`, {
      headers: { apikey: SUPABASE_PUBLISHABLE_KEY! },
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { external?: Record<string, boolean> };
    return {
      google: Boolean(body.external?.google),
      email: Boolean(body.external?.email),
    };
  } catch {
    return null;
  }
}
