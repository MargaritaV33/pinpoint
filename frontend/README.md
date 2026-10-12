# Pinpoint — frontend

React + TypeScript + Vite single-page app for Pinpoint (client feedback on
architectural visualization renders). Prototyped in Lovable, imported into
this repo and adapted to run on npm. See the root
[`product-spec.md`](../product-spec.md) for what the app does and
[`AGENTS.md`](../AGENTS.md) for repo-wide rules.

## Run

```sh
npm install
npm run dev
```

Opens the Vite dev server (TanStack Start in client-only SPA mode — see
"Architecture" below). The app loads with the mock API client by default, so
no backend is required.

## Test

From the repository root:

```sh
make frontend-test
```

or, directly inside `frontend/`:

```sh
npm test
```

Runs the Vitest suite (pin-coordinate math, pin filtering, the mock API
client, and app routing).

## Build

```sh
npm run build
```

Produces a static production bundle (TypeScript is checked as part of the
build; there are no type errors in a passing build).

## Mock vs. HTTP client

All backend calls go through the single typed `ApiClient` interface in
`src/lib/api/` (`src/lib/api/client.ts`). Two implementations exist:

- `MockApiClient` (`src/lib/api/mock.ts`) — the **default**. Backed by
  `localStorage` with seeded demo data (`src/lib/api/mock-seed.ts`), so the
  whole app runs with no backend. A studio tab and a guest tab in the same
  browser see each other's changes through the existing 3-second polling
  (`src/lib/queries.ts`).
- `HttpApiClient` (`src/lib/api/http.ts`) — a **stub**, not yet wired to a
  real backend. It is written against the same `ApiClient` interface and
  will start working once the backend exists (see issue #5, "Connect
  frontend and backend").

The switch is the `VITE_API_BASE_URL` environment variable
(`src/lib/api/index.ts`): unset (the default) selects the mock client; set it
to the backend's base URL to select the HTTP client. This matches the root
`.env.example`.

## Demo data

- Studio login: `demo@pinpoint.studio` / `pinpoint` (prefilled on the sign-in
  screen).
- Guest links (client side, no login): `/g/lakeside-demo` and
  `/g/atrium-demo`.

## Architecture

- Client-side SPA: `src/start.ts` sets `defaultSsr: false`. No backend or
  server functions live here — the backend is a separate FastAPI service
  built from `openapi.yaml` in later issues.
- All backend calls go through the `ApiClient` interface in `src/lib/api/`
  (`api`, exported from `src/lib/api/index.ts`); nothing outside
  `src/lib/api/` calls the network.
- Pin coordinates are percentages (0–100) of the image box; all click ↔
  percent math lives in `src/lib/pins/coords.ts` (pure, tested).
- Live updates use TanStack Query's `refetchInterval` polling
  (`src/lib/queries.ts`), not WebSockets.
- Routing is TanStack Router's file-based routing under `src/routes/` (see
  `src/routes/README.md` for conventions). `src/routeTree.gen.ts` is
  generated — do not edit it by hand.
- Styling is Tailwind CSS v4 + shadcn/ui (`src/components/ui/`), with Inter
  loaded from Google Fonts in `src/routes/__root.tsx`.

## Known dev-server noise

While running `npm run dev`, a hard reload or navigation away mid-load can
print a trace like:

```
Error: aborted
    at abortIncoming (node:_http_server:845:17)
    at socketOnClose (node:_http_server:839:3)
    at Socket.emit (node:events:520:35)
    at TCP.<anonymous> (node:net:346:12) (status 500)
```

(Reproduced directly: aborting an in-flight request to the dev server —
e.g. a client closing the connection before the response finishes — prints
exactly this, with no application code anywhere in the stack. It still
happens after the studio/guest image-rendering fixes in this issue, so it
was never caused by the `401`/broken-image bug — it is an inherent
property of Node's own HTTP server reacting to a client-closed socket.)

This comes from Node's own `http.Server` (`node:_http_server`), one layer
below TanStack Start's dev middleware and below `src/server.ts`'s own
try/catch — it fires when the client's TCP socket closes while the server
is still writing a response, which `server.ts`'s wrapper has no way to
intercept (it isn't a thrown error reaching its `fetch()` call). We looked
for a supported way to suppress specifically this trace — the
`@lovable.dev/vite-tanstack-config` wrapper's own option surface
(`vite`, `tanstackStart`, `serverFnErrorLogger`, `ssrErrorLogger`, `nitro`,
…), Vite's dev-server options (`clientError` handling is for malformed
*incoming* requests, not a response aborted mid-write), and Nitro/h3 (which
only runs at build time for this app's `spa: { enabled: true }` setup —
`npm run dev` serves requests through Vite's own dev middleware, not a
built Nitro server) — and found no config knob that targets it. It is safe
to ignore: it is purely a dev-server console artifact of the client
disconnecting, not a real server error, and a genuine thrown `500` still
logs normally (`server.ts`'s wrapper still catches and renders its error
page for those).
