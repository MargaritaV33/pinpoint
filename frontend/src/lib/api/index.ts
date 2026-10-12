import type { ApiClient } from "./client";
import { createHttpApi } from "./http";
import { createMockApi } from "./mock";

export type { ApiClient } from "./client";
export * from "./types";
export { validateRenderFile, MAX_RENDER_BYTES } from "./validation";

const baseUrl = import.meta.env["VITE_API_BASE_URL"] as string | undefined;

/** The app-wide client. Set VITE_API_BASE_URL to talk to the FastAPI service. */
export const api: ApiClient = baseUrl
  ? createHttpApi(baseUrl)
  : createMockApi({
      storage: () => (typeof window === "undefined" ? null : window.localStorage),
      latencyMs: 120,
    });
