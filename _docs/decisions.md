# Decisions

Taken on 12 Oct 2026 during the spec session. Reopen only explicitly.

| Topic | Decision | Reason |
|-------|----------|--------|
| Users | Studio has accounts; client uses a guest link with a display name | Zero friction for clients; matches how studios share work |
| Room | One room = one delivery round with many images, one link | Matches real deliveries (a batch of views) |
| Pin | Point stored as % of width/height; number per image; type fix / question / like; status open / resolved (like has none) | Survives resizing; types make the export useful |
| Rounds | No versioning in v1; new render = new image, old one `superseded` | Versioning is a day of work; see _local/make-it-better #1 |
| Updates | Light polling, no WebSockets | Simpler, nothing extra to break on Render; _local/make-it-better #2 |
| Upload | Real upload from day 1, JPG/PNG ≤ 15 MB, bytes stored in the database | Render's disk is ephemeral; it is the demo |
| Extras | Client **Approve round** button and open-pin export are in v1 | Cheap and useful |
| Frontend | React + TypeScript + Vite, prototyped in Lovable, single API client in `src/lib/api/` | Course default; Lovable for a good-looking demo |
| Backend | FastAPI + uv + SQLAlchemy, modules routers / models / store / auth | Course default; reviewers expect it |
| Database | SQLite locally, Postgres in Compose and production, via `DATABASE_URL` | Rubric: supports different environments |
| Containers | One two-stage image (Node builds frontend, Python serves it) + Postgres in Compose | Course default |
| Deployment | Render (web service + managed Postgres) for attempt 1; AWS/CloudFormation considered for attempt 2 | Fastest path to a public URL |
| CI/CD | GitHub Actions: backend + frontend tests in parallel → compose stack → integration + e2e → deploy → health check | Rubric criterion 11 |
| Scope guard | Options Room and anything client-portal-shaped stays out of this repo | Private product value |
| Scope statement | The app is deliberately small: the point of the project is to exercise the full AI-native workflow (spec → contract → tests → containers → CI/CD → ops → agent extensions) end to end, not to ship a feature-complete product. The README says so explicitly. | Course rubric scores workflow discipline, not feature count |
| Comment edit/delete | Out of v1, stays in _local/make-it-better #3 even after submission | Immutable threads keep the history trustworthy |
