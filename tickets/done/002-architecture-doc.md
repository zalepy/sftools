# 002 — Add ARCHITECTURE.md

**Type:** docs · **Priority:** P1 · **Depends on:** 001 · **Status:** Done

> **Update (2026-10-11):** See `ARCHITECTURE.md`.

## Content
- [ ] **Overview:** what the tool does (Satisfactory production planner), and the main parts: data scraping → loader → engine → API → UI
- [ ] **Module map** for `src/sftools/` (one line per package) and what each one is responsible for
- [ ] **Data flow** for a request: `/api/calculate` → `calculate_demands` → `FactoryGraph` → `get_ui_data` → Cytoscape
- [ ] **Graph model:**
  - master graph vs. UI graph
  - merges (`absorbed_by`), dormancy, overrides
  - captured starting structure and rebuild on unmerge
  - Fold in the relevant parts of `ALGO.md` and link to it.
- [ ] **State model:** what lives on the client (localStorage), what lives on the server, and what is re-sent on each request (see 010)
- [ ] **Node identity:** path-based IDs and their limits (see 016)
- [ ] **API reference table:** endpoint, method, purpose, payload
- [ ] **Deployment:** local dev vs. Render, environment variables
- [ ] Short **decision log** (src layout, one app serving UI + API at the same origin, uv)
