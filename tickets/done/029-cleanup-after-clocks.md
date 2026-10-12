# 029 — Cleanup: API round-up, fixed scales, legacy engine paths and tests

**Type:** tech debt · **Priority:** P2 · **Status:** Done · **Related:** 010, 023

> **Done (2026-10-12).** Everything below except the optional inline-style move. `build_plan(exact=True)` replaces `round_up=False`. One dormancy walker remains, `set_subtree_dormancy`, over the unmerged structure. The seven stateful-era test files are gone. What they still covered moved through `build_plan`: tree structure and IDs, merged links in the UI data, unmerge restoring the plan exactly (`test_graph_state`), and a clock changing only its own node (`test_clocks`). Several of their assertions had never run: they looked for an item called "Screw", while the data says "Screws". Unit tests: 130, down from 152, with the same behaviour covered.

Leftovers from the stateful API (before 010) and from building overrides (before 023). Nothing here changes what the user sees.

## API
- [x] **Remove `round_up` from `PlanRequest`:** the API always rounds. `build_plan` keeps an exact mode for the unit tests' balance checks, renamed so it reads as what it is (e.g. `exact=True`).
- [x] **Remove `overrides` from `PlanRequest`** and the UI's `state.overrides` carrier. Saved plans were migrated with a notice on first load after 023. A plan that still has the key would then have it ignored without a notice (pydantic ignores unknown fields).

## Engine
- [x] **Fixed scales:** `ProductionNode.user_scale` and `FactoryGraph.recalculate(overrides)`. No plan can set them since 023; only low-level tests use them (18 references). Remove them, and rewrite those tests with clocks or exact demands.
- [x] **Unused:** the `scale_overrides` parameter of `calculate_demands`, `FactoryGraph.recipe_overrides`, and the `recalculate_graph` wrapper (19 test uses; call `graph.recalculate` instead).
- [x] **In-place unmerge:** `remove_merge` / `_rebuild_structure` belong to the stateful API. Stateless, an unmerge is a plan without that merge, and only tests use them. Same for `capture_initial_structure` (hand-wired test graphs): keep it only if the remaining tests need it.
- [x] **Two dormancy walkers:** `set_subtree_dormancy` (follows the merged links) and `drop_subtree` (follows the unmerged structure). Keep one, the unmerged-structure one, unless a recipe switch needs the other.
- [x] Docstrings and ARCHITECTURE/ALGO lines that describe removed paths.

## Tests
- [x] **Consolidate the stateful-era files:** `test_persistence.py`, `test_interactive_graph.py`, `test_recalculate.py`, `test_factory_graph.py`, `test_production_node_graph.py`, `test_scale_inflation.py`, `test_demand_calculator.py` (22 tests). Many drive `calculate_demands` + `recalculate_graph` directly with `round_up=False`. Keep what each still covers, through `build_plan` where possible, and move it into the topic files (`test_merges`, `test_splits`, `test_clocks`, `test_graph_state`). Drop what newer tests already cover.
- [x] Afterwards, `round_up=False` (or `exact=True`) appears only where a test checks balances.

## Frontend
- [x] Unused CSS: `.toggle-switch` (the round-up toggle is gone).
- [ ] Inline styles in `index.html` that could live in `app.css` (optional; touches many lines).

## Done when
All tests pass with the same coverage of behaviour, the API has no `round_up` or `overrides`, and `user_scale` no longer exists.
