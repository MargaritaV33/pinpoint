# Two-stage build: Node builds the frontend into a static bundle, Python
# serves the API and that bundle from the same origin (no CORS needed). See
# _docs/decisions.md's "Containers" row and issue #8.

# ---- Stage 1: frontend-build ------------------------------------------
FROM node:22-slim AS frontend-build
WORKDIR /frontend

# Lockfile is already committed. Issue #8 shipped `npm install` here because
# the then-committed package-lock.json (generated on a Windows dev machine)
# was missing linux-only optional transitive entries. Issue #9 regenerated
# the lockfile once, on Linux, so it's now complete for linux/amd64 and
# `npm ci`'s strict lockfile-sync check passes again — back to `npm ci` for
# reproducible installs. This is a one-time fix to the committed lockfile's
# content, not a build-time step: this stage must not regenerate the
# lockfile on every build, which would reintroduce the non-determinism
# `npm ci` exists to prevent.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .

# Baked in at build time: Vite inlines VITE_API_BASE_URL into the built JS
# during `npm run build`, so this is the one place that sets it for the
# Docker image. "" selects the HttpApiClient against the page's own origin
# (see frontend/src/lib/api/index.ts) — same-origin, no CORS. Overriding it
# later (docker run -e / compose environment:) does nothing; rebuild with a
# different --build-arg instead.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ---- Stage 2: backend + served frontend --------------------------------
FROM python:3.12-slim

# requires-python = ">=3.11" in backend/pyproject.toml; 3.12-slim satisfies it.
RUN pip install --no-cache-dir uv

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock backend/
RUN cd backend && uv sync --frozen --no-dev

COPY backend/ backend/

# backend/tests/test_openapi_contract.py resolves the contract file as
# `Path(__file__).resolve().parents[2] / "openapi.yaml"` — i.e. two levels
# above backend/tests/, which is this image's /app when backend/ lives at
# /app/backend/. Only the backend-test service (profiles: ["test"]) ever
# runs pytest inside this image, but the file is tiny and harmless to carry
# in the production `app` image too, so one COPY covers both.
COPY openapi.yaml /app/openapi.yaml

# frontend/.output/public is the static build output (confirmed from
# docs/ai-usage-report.md and frontend/vite.config.ts's tanstackStart.spa
# comment); _shell.html inside it is the SPA shell FastAPI falls back to.
COPY --from=frontend-build /frontend/.output/public /app/frontend_dist

WORKDIR /app/backend
EXPOSE 8100
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
