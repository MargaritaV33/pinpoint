// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
    // defaultSsr: false (src/start.ts) makes this a client-only SPA; `spa.enabled`
    // makes `npm run build` prerender one static shell (index.html) that is served
    // for every path, so the build output needs no server process to run — it can
    // be served as plain static files (matches this repo's deployment: FastAPI
    // serves the built frontend, see AGENTS.md).
    spa: { enabled: true },
  },
  // Vite only loads .env* files from its own project root (frontend/) by
  // default, but VITE_API_BASE_URL is documented only in the repo-root
  // .env.example (the repo keeps exactly one). Point envDir at the repo
  // root so `npm run dev`/`npm run build` here pick up a root-level .env.
  vite: {
    envDir: "../",
    // The wrapper's own non-sandbox default is server.port: 8080, with a
    // fallback to 8081/8082 etc. if busy — non-deterministic across
    // machines/runs, and not what .env.example's CORS_ORIGINS default or
    // README.md assume. Pin the dev server to Vite's documented default,
    // 5173, and fail loudly (strictPort) instead of silently drifting to
    // another port, so CORS_ORIGINS's default origin stays correct.
    server: {
      port: 5173,
      strictPort: true,
    },
  },
});
