# 049 — User guide, in the repo and in the app

**Type:** docs · **Priority:** P2 · **Status:** Done

## Goal
A user guide that explains how to use each feature, with examples and screenshots. It's one Markdown file, shown by GitHub and in the app's Guide panel. The README becomes a short introduction that links to it.

## Decisions (agreed with the user, 2026-10-22)
- **Single source:** `src/sftools/web/guide/USER_GUIDE.md`, with its screenshots in `images/` next to it. It lives inside the package because the app serves it. ARCHITECTURE.md, ALGO.md and the tickets stay where they are.
- **Rendering:** by the server, with the `markdown` package, once at startup. Nothing is loaded from a CDN.
- **Screenshots:** made by `scripts/screenshots.py`, using the browser-test harness. Rerun it to refresh them all.
- **Panel:** a Guide button next to Legend opens a fixed-width drawer over the graph, with a contents list. Opening Guide closes Legend and the other way round; the Legend stays its own panel.
- **"?" links** by sections of the side panel (and in the zoomed-in logistics and Chain toolbars) open the guide at the matching section.
- **Examples:** plain text, with no "Try it" buttons.

## Notes
- Implemented 2026-10-22: `api/guide.py` and the `/guide` and `/guide/images/` routes; `static/js/guide.js`.
- Heading ids match GitHub's, so `#section` links work in both places. Image paths are relative to the file; the server rewrites them to `/guide/images/`. Links to other sites open in a new tab.
- Only the images are served, not the Markdown itself.
- A guide that doesn't render fails startup, as bad game data does.
- The worked example (10 Modular Frames a minute) uses numbers checked against the calculator.
- Tests: `tests/unit/test_guide.py` (images and links resolve; every "?" points to a section; served rendered) and `test_guide_panel` in `tests/integration/test_ui.py`.
