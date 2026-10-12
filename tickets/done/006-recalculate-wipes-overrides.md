# 006 — Merging or switching a recipe clears manual overrides

**Type:** bug · **Priority:** P1 · **Status:** Done

> **Update (2026-10-11):** The stateless API (010) always applies overrides last in `build_plan`, so users no longer lose them. `FactoryGraph.recalculate(None)` still clears them; fix it when the engine is next touched.

> **Fixed (2026-10-11):** `FactoryGraph.recalculate(overrides=None)` now keeps the current overrides; pass `{}` to clear them. Merges and recipe switches no longer wipe them. Tests: `tests/unit/test_graph_state.py`.

## Problem
`FactoryGraph.recalculate(overrides=None)` resets every node's `user_scale` to `None`.
`api_merge_nodes` passes `None` with the comment "Preserve existing overrides", and `switch_recipe_in_graph` calls `recalculate()` without overrides. Both silently clear the user's manual scales.

## Fix
- [ ] Separate the two meanings: `None` = keep the current overrides; `{}` = clear them all
- [ ] Or keep the overrides as graph state (`self.overrides`), as is done for merges
- [ ] Tests: merge and recipe switch both keep an override set elsewhere in the graph
