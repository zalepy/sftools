# 017 — Split the 1,400-line index.html

**Type:** refactor · **Priority:** P3 · **Depends on:** 001 · **Status:** Open

- [ ] Move CSS and JS out to `web/static/` (`app.css`, `graph.js`, `panel.js`, `state.js`, `api.js`), served via `StaticFiles` at `/static`
- [ ] Load third-party libraries from pinned CDN versions, or vendor them
- [ ] No build step needed yet: plain ES modules
