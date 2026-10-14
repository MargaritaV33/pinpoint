# Deployment

Pinpoint deploys to [Render](https://render.com) as a Blueprint: one web
service (the Dockerfile image already built and verified in #8/#9) plus one
managed Postgres database, both described in root `render.yaml`. This repo
does not deploy itself — a human with Render dashboard access applies the
Blueprint once; see "Creating the Blueprint" below.

## Creating the Blueprint

1. Open the Render dashboard and click **New +**, then **Blueprint**.
2. Connect or select the `MargaritaV33/pinpoint` GitHub repo, granting the
   Render GitHub App access to it if this is the first time.
3. Render reads `render.yaml` from the repo root and shows a preview of the
   resources it will create: one web service (`pinpoint`) and one Postgres
   database (`pinpoint-db`).
4. Review the preview — both resources should show plan **Free**.
5. Click **Apply**.
6. Wait for the web service to reach **Live**, then confirm its
   `*.onrender.com` URL returns `200` at `/health`.

No other dashboard configuration is needed: every environment variable the
app requires is either generated, wired from the attached database, or
relies on a working default (see the table below), and no build command,
pre-deploy command, or extra service is required. `render.yaml` sets no
command override, so the only command Render runs is the Dockerfile's own
`CMD`.

### No migration step

This deployment adds no migration step and no new seeding mechanism. The
app's own startup path — `SQLAlchemyStore.__init__` in
`backend/app/store/sqlalchemy/db_store.py` — already runs
`Base.metadata.create_all` unconditionally and then `_seed()` only if the
database is empty, on every boot. That path is already exercised against
real Postgres (issues #6/#8/#9) and needs nothing Render-specific.

## Environment variables

One row per field in `backend/app/config.py`'s `Settings`:

| Setting | Render var | How it's set |
|---|---|---|
| `database_url` | `DATABASE_URL` | Set automatically by the blueprint — wired via `fromDatabase` to the `pinpoint-db` database's `connectionString`. Render supplies a bare `postgres://` or `postgresql://` URL; `Settings._normalize_database_url` (a `field_validator` on `database_url` in `backend/app/config.py`) rewrites either form to `postgresql+psycopg://`, because this backend installs `psycopg[binary]`, not `psycopg2`. `render.yaml` does no rewriting. `sqlite:///...` and already-qualified `postgresql+psycopg://...` URLs pass through unchanged. |
| `jwt_secret` | `JWT_SECRET` | Set automatically by the blueprint — `generateValue: true`, a random value Render generates and stores; never Compose's local-dev default. |
| `environment` | `ENVIRONMENT` | A fixed literal, `production`, written directly in `render.yaml`. It is a free-form label read nowhere else in the codebase, so a literal is safe. |
| `access_token_minutes` | `ACCESS_TOKEN_MINUTES` | Relies on its working default (`60`) — not set in `render.yaml`; already a reasonable production value. |
| `cors_origins` | `CORS_ORIGINS` | Relies on its working default (the two local-dev origins) — not set in `render.yaml`; irrelevant in production because the frontend is served same-origin by this same image (issue #8), so no browser request ever needs a CORS allowance here. |
| `max_upload_mb` | `MAX_UPLOAD_MB` | Relies on its working default (`15`) — not set in `render.yaml`; this is the product-spec limit itself. |

Nothing in this deployment requires a human to type in a value:
`JWT_SECRET` is generated, `DATABASE_URL` is wired from the attached
database, `ENVIRONMENT` is a fixed literal in the file, and every other
variable relies on its documented default.

The frontend needs no runtime configuration either: `VITE_API_BASE_URL` is
baked into the image at build time as `""` (same-origin), per the
Dockerfile comment from issue #8, so it does not appear in `render.yaml` at
all.

## Rollback

Render's own UI is the only rollback mechanism this project uses — there is
no CLI rollback on the free plan, and this project does not add one.

To roll back: open the `pinpoint` web service, go to its **Deploys** tab,
find a previous deploy marked successful, and use that deploy's
**Redeploy** action.

## Free plan limits

Both resources in `render.yaml` use Render's free plan deliberately (see
`_docs/decisions.md`'s "Deployment" row). Two limitations are accepted as
part of that choice, not open problems:

- The free web service spins down after a period of inactivity, so the
  first request after idling pays a cold-start delay while it spins back
  up.
- Render's free Postgres databases expire 30 days after creation unless
  upgraded to a paid plan.

See `docs/testing.md` for how the app is verified before it ever reaches
Render, and `_docs/decisions.md` for why Render (over AWS/CloudFormation)
was chosen for this first deployment attempt.
