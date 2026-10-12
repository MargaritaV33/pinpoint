/**
 * Placeholder for the single API client the frontend talks to the backend
 * through (per AGENTS.md: "All frontend calls to the backend go through the
 * single client in frontend/src/lib/api/. Nothing else talks to the
 * network.").
 *
 * No network calls are made yet. Real requests start in a later issue, once
 * `openapi.yaml` exists and the backend has endpoints to call.
 */

export interface ApiClient {
  baseUrl: string
}

export function createApiClient(): ApiClient {
  return {
    baseUrl: '',
  }
}
