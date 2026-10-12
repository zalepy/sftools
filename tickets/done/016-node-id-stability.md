# 016 — Path-based node IDs are long and fragile

**Type:** tech debt · **Priority:** P3 · **Related:** SPLIT_PLAN.md · **Status:** Done

> **Done (2026-10-12):** Item-path IDs; see ARCHITECTURE.md, "Node identity".
> - **Why the parent recipe was in the ID:** it was added with recipe switching (`09f1c94`, the "isolated scheme"). Switching a node's recipe gives its inputs new IDs, so adjustments below a switch reset and return on switching back. **Kept on purpose.**
> - **Format:** `Smart Plating__Reinforced Iron Plate__Screws`. The parent's recipe is included only when it isn't the default (`…__Alternate: Bolted Iron Plate>Screws`). The longest ID went from 188 to under 120 characters.
> - **Roots** are keyed by item. A repeated item gets `#2`, which **fixes a bug**: two demand rows for the same item collided on one ID, and one row's rate was lost.
> - **Old saved plans:** old-style IDs are no longer matched. They're reported in `ignored` and dropped once (with the notice); there is no migration (decision 2026-10-12).
> - **UI:** labels for a consumer now read "<item> (in <item it feeds>)".
> - **Tests:** `tests/unit/test_graph_state.py` (ID shape, duplicate roots, reset below a switch, old IDs reported).
> - **For splits** (SPLIT_PLAN.md): use an instance suffix in the same `#n` style.

- IDs look like `root_0__Recipe__[r]Recipe__Recipe…` and grow with depth.
- Any upstream change (a recipe switch, a different root order) invalidates the saved merges and overrides below it.

## Tasks
- [ ] Decide on an ID scheme before implementing splits (e.g. stable hash of (root key, path of item names) + instance index)
- [ ] Root keys should be based on the item, not on its list position (`root_{i}`), so removing a root doesn't renumber the others
