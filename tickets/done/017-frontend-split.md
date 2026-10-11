# 017 — Split the 1,400-line index.html

**Type:** refactor · **Priority:** P3 · **Depends on:** 001 · **Status:** Done

> **Done (2026-10-11):** `index.html` is down from 1,415 to about 220 lines of markup.
> - **CSS:** `web/static/app.css`.
> - **JS:** ES modules in `web/static/js/`:
>   - `api.js`: server calls
>   - `state.js`: plan state, localStorage, export/import
>   - `graph.js`: Cytoscape, zoom, drag-to-merge
>   - `panel.js`: sidebar, node details, recipe picker, colours tab, notice
>   - `main.js`: plan actions and wiring
> - The 15 inline `onclick`/`onsubmit`/`onchange` handlers are now `addEventListener` calls; demand rows use event delegation.
> - Sidebar content is built with the DOM API instead of `innerHTML`, so item names from imported files are inserted as text.
> - **Serving:** `/static` is mounted with `Cache-Control: no-cache` (ETag revalidation), and the page adds `?v=<hash of static files>` to its CSS/JS URLs, so a deploy is picked up right away.
> - The CDN libraries were already pinned (cytoscape 3.28.1, dagre 0.8.5, cytoscape-dagre 2.5.0).
> - **Small fixes along the way:** colours load before the saved plan is drawn; the status-dot style is limited to nodes that have one (no more Cytoscape warnings); inline favicon (no more `/favicon.ico` 404).
> - **Verified:** a headless Chrome run covering calculate, add/remove rows, node selection, recipe switch, override and clear, merge/unmerge, stale-plan notice, colours tab and fit view, with no JS errors or warnings. `test_static_assets_are_served` checks the static files are served correctly.

- [ ] Move CSS and JS out to `web/static/` (`app.css`, `graph.js`, `panel.js`, `state.js`, `api.js`), served via `StaticFiles` at `/static`
- [ ] Load third-party libraries from pinned CDN versions, or vendor them
- [ ] No build step needed yet: plain ES modules
