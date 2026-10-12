import type { ApiClient } from "./api/client";
import { ApiError } from "./api/types";

export type AuthMode = "signin" | "signup";

/** Shown for anything that isn't an `ApiError` — a thrown `Error`, a
 * network failure, or anything else. `ApiError.message` already carries
 * the backend's `detail` text verbatim, so only that case is safe to show
 * to the user directly. */
export const AUTH_FALLBACK_ERROR = "Something went wrong. Please try again.";

export type AuthFormResult = { ok: true } | { ok: false; message: string };

/**
 * Picks `signup` vs `login` from `mode`, and turns whatever the call throws
 * into a message safe to render in the form. Pure apart from the `api`
 * call itself — no DOM, no router — so it's unit-testable without
 * rendering `login.tsx`.
 */
export async function submitAuthForm(
  mode: AuthMode,
  email: string,
  password: string,
  api: Pick<ApiClient, "signup" | "login">,
): Promise<AuthFormResult> {
  try {
    if (mode === "signup") {
      await api.signup(email, password);
    } else {
      await api.login(email, password);
    }
    return { ok: true };
  } catch (err) {
    return { ok: false, message: err instanceof ApiError ? err.message : AUTH_FALLBACK_ERROR };
  }
}
