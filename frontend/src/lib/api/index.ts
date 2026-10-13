import type { ApiClient } from "./client";
import { createHttpApi } from "./http";
import { createMockApi } from "./mock";

export type { ApiClient } from "./client";
export * from "./types";
export { validateRenderFile, MAX_RENDER_BYTES } from "./validation";

const baseUrl = import.meta.env["VITE_API_BASE_URL"] as string | undefined;

/**
 * The app-wide client. Set VITE_API_BASE_URL to talk to the FastAPI service.
 *
 * Checked against `undefined` specifically, not truthiness: an explicitly
 * empty string (`VITE_API_BASE_URL=""`, baked in at Docker build time for
 * same-origin requests) must select `HttpApiClient` with an empty base URL,
 * not fall through to the mock client the way `baseUrl ? ... : ...` would
 * (`""` is falsy in JS). Only a genuinely *unset* var (local `npm run dev`,
 * no `.env`) keeps selecting the mock client.
 */
export const api: ApiClient =
  baseUrl === undefined
    ? createMockApi({
        storage: () => (typeof window === "undefined" ? null : window.localStorage),
        latencyMs: 120,
      })
    : createHttpApi(baseUrl);
