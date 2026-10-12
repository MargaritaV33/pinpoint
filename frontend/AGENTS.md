<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Architecture rules
- Client-side SPA: `defaultSsr: false` in src/start.ts; no Lovable Cloud/server functions — backend is a separate FastAPI service.
- All backend calls go through the `ApiClient` interface in src/lib/api/ (`api` from src/lib/api/index.ts); nothing outside src/lib/api may call the network. Mock (localStorage, seeded) is used unless VITE_API_URL is set.
- Pin coordinates are percentages (0–100) of the image box; all click↔percent math lives in src/lib/pins/coords.ts (pure, tested).
- Live updates via react-query `refetchInterval` polling (src/lib/queries.ts), not websockets.
