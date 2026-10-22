# 052 — Split panel.js and main.js; guidance on where code goes

**Type:** refactor · **Priority:** P3 · **Status:** Done

## Goal
No front-end module so big that it's hard to find things in it, and a written rule on where new code goes, so they don't grow back. `panel.js` (899 lines) held every side-panel section; `main.js` (837) held every plan action plus the wiring.

## Decisions (agreed with the user, 2026-10-22)
- Split by tab and section, no behavior change; the browser tests are the safety net.
- `engine/logistics.py` (876 lines) stays whole: one algorithm in one place, explained in ALGO.md.
- **The guidance lives in `CLAUDE.md`** (repo root): what goes in `main.js`, `actions/`, `panel/` and the pure modules, the import direction, and the 500-line limit. Claude Code reads it at the start of every session, so it steers new work without anyone reviewing the front end's structure. ARCHITECTURE.md links to it.
- **`scripts/check_sizes.py`** in CI warns (doesn't fail) about files over 500 lines, with a short list of files allowed over it and why.

## Notes
- Implemented 2026-10-22:
  - `main.js` (182): wiring and startup only.
  - `actions/`: `plan.js` (request, render, save, plan-wide actions), `node.js`, `tabs.js`, `logistics.js`, `notes.js`, `preferences.js`.
  - `panel/`: `common.js`, `shell.js` (tabs, collapsing, legend), `messages.js` (toast, plan notice), `planner.js`, `node.js`, `move-branch.js`, `selection.js` (edge, by-product, logistics), `recipes.js`, `colors.js`. The largest is `panel/node.js` (284).
  - `graph.js` 685 → 457: the stylesheet moved to `graph-style.js`, node text and colors to `node-info.js`. `logistics.js` 601 → 515: placement moved to `logistics-placement.js`; it stays on the allowed list (the view's editing, one concern).
- All 62 browser tests, 128 Python and 22 JS unit tests pass.
- `check_sizes.py` also flags `domain/models/factory_graph.py` (614 lines). Left as a warning, for the back end's owner to decide.
