/* Access-token bridge between the auth context and the API client.

   The API client attaches "Authorization: Bearer <token>" to protected
   requests; tokens live only in memory here (Supabase-js persists the
   session itself). 401 responses trigger registered handlers so the app can
   attempt a session refresh and otherwise bounce to sign-in. */

let accessToken: string | null = null;
const unauthorizedHandlers = new Set<() => void>();

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function onUnauthorized(handler: () => void): () => void {
  unauthorizedHandlers.add(handler);
  return () => unauthorizedHandlers.delete(handler);
}

export function notifyUnauthorized(): void {
  for (const handler of unauthorizedHandlers) handler();
}
