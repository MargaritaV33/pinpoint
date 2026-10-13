# Pinpoint end-to-end tests

Playwright tests that drive a real Chromium browser against the real
`docker compose` stack (no mocks, no dev server), covering the same
flows as `_docs/test-scenario.md`: a studio and a guest reviewing renders
in two separate browser contexts.

## Setup

```
npm install
```

(This is a standalone Node project — its own `node_modules`, not a
frontend workspace member.)

## Running

`npx playwright test` runs the suite headlessly. This is **not** the same
as `make e2e` (see the root `Makefile`): running Playwright directly here
does not install Chromium, detect, start, or tear down the compose stack
for you — **the stack must already be running** (`make up` from the repo
root) before you run any of the commands below. `make e2e` wraps all of
that; use it from the repo root when you just want the suite to run
end to end without thinking about the stack's lifecycle.

```
npx playwright test
```

Watch it drive real browser windows instead of running headless:

```
npx playwright test --headed
```

Step through a test interactively with the Playwright Inspector:

```
npx playwright test --debug
```

or equivalently:

```
PWDEBUG=1 npx playwright test
```

Open the HTML report from the last run:

```
npx playwright show-report
```

Open a trace kept from a failed run (traces are retained only on
failure, per `playwright.config.ts`; the path is printed in the test
output and also linked from the HTML report):

```
npx playwright show-trace <path-to-trace.zip>
```

## Stack detection and teardown contract (`make e2e`)

`make e2e` (`cd e2e && npm install && node scripts/run.mjs`) runs
`e2e/scripts/run.mjs`, which:

1. Installs the Chromium browser binary (`npx playwright install
   chromium`) — a no-op if it's already present.
2. Checks `GET /health` on the app (`http://localhost:${APP_PORT:-8100}/health`).
   If it's already up, the script leaves it alone. If not, it starts the
   stack itself with the same command `make up` runs
   (`docker compose up -d --build --wait`).
3. Runs `npx playwright test`.
4. If (and only if) this script started the stack in step 2, it tears it
   down afterward with the same command `make down` runs
   (`docker compose down -v`). If the stack was already running when the
   script started, it is left running, untouched.
5. Exits with the test run's exit code, not teardown's.

So `make e2e` is safe to run whether or not you already have the stack up
— it always leaves things exactly as it found them.
