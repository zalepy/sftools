# 007 — Unmerge or rebuild disconnects subtrees created by a recipe switch

**Type:** bug · **Priority:** P1 · **Status:** Done

> **Update (2026-10-11):** The stateless API (010) rebuilds the graph from scratch on every request and no longer calls `remove_merge`, so this can't happen through the UI. The bug is still in `FactoryGraph._reset_structure`.

> **Fixed (2026-10-11):** `FactoryGraph.link(parent, child)` records every link in the unmerged structure as it is made, including links from `expand_new_subtree`, so `_reset_structure` restores them. `calculate_demands` no longer needs `capture_initial_structure`. Tests: `tests/test_graph_state.py` (switch → unmerge, switch → merge → unmerge round trip).

## Problem
`capture_initial_structure()` runs only once, at the end of `calculate_demands`. Nodes and links added later by `expand_new_subtree` are not in `_initial_structure`, so `_reset_structure()` (called on every unmerge) clears their links and never restores them.

Reproduced: switch the root of a Screws graph to *Alternate: Cast Screws*, then call `remove_merge` → the root has 0 active children (expected: `[Iron Ingot]`).

## Fix
- [ ] Record new nodes and links in the saved structure when a subtree is expanded
- [ ] Or rebuild the structure from the saved operations (recipe switches + merges) instead of a one-time snapshot
- [ ] Regression test for switch → merge → unmerge
