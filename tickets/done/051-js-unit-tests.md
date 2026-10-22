# 051 — Unit tests for the front end's pure logic

**Type:** test · **Priority:** P3 · **Status:** Done

## Goal
The front end's rules and calculations tested in milliseconds, without a browser. Until now, the only tests were through the page (e.g. the fit-clock rule ran 11 browser tests to check one function).

## Decisions (agreed with the user, 2026-10-22)
- **Node's built-in test runner** (`node --test`): no npm, no `package.json`, no packages. CI already had Node.
- **Pure modules:** a calculation moves into a module that touches neither the DOM nor Cytoscape, so Node can import it. DOM code stays thin around it.

## Notes
- Implemented 2026-10-22 with ticket 052, which created the pure modules:
  - `clocks.js`: `fitLastClock` (ticket 047), plus `clockGroups` and `clockBoxes`, which turn the Node tab's clock boxes into groups and back (they were inline in the panel before).
  - `node-info.js`: text colors, the status dot, clocks and buildings as text, built marks (from `graph.js`).
  - `logistics-placement.js`: where the zoomed-in logistics view puts its nodes (from `logistics.js`); it now takes the side's data instead of reading module state.
- `tests/js/*.test.mjs`, 22 tests. The fit-rule cases moved there from `tests/integration/test_fit_clock.py`, which keeps the tests of the button itself (browser tests: 73 → 62).
- Also a Python check (`test_module_imports_resolve`) that every JS import names an export that exists, so a refactor that drops or renames one fails in a second instead of in the browser tests.
