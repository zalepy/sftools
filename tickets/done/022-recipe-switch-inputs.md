# 022 — Recipe switch: keep shared inputs, drop unused branches

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** 016, 020

> **Done (2026-10-12).** Option B, as decided by the user. "(A)" marks alternate recipes only; other kinds of recipe may get their own markers when needed.

## Problem
Switching a merged Screws node to Cast Screws left the absorbed branch's Iron Rod → Iron Ingot → Iron Ore chain on the graph at 0/min, still linked to the merged node. The same happened when merging nodes that run different recipes. There was also no sign on the graph of which nodes run an alternate recipe.

## Behaviour
- **Shared inputs** (used by both the old and the new recipe) keep their node and its adjustments (override, merges, splits, recipe); their numbers are recalculated.
- **Inputs the new recipe doesn't use** are dropped with everything under them, unless something else still needs them: if a dropped input is part of a merge, the rest of the group stays merged, and only this branch's share goes.
- **New inputs** are built as in the initial graph.
- **Adjustments on dropped inputs are discarded**: switching back builds the input as a fresh branch, unconnected to any earlier merge. (Before, they were kept for switching back.)
- A merge group runs its target's recipe, so the absorbed nodes' inputs it doesn't use are dropped the same way.
- Nodes running an alternate recipe are labelled "(A)" on the graph.

## Implementation
- `child_node_id` no longer puts the recipe in the ID: an input is `<parent id>__<item>` whatever recipe the parent runs. A switch reactivates the old recipe's inputs that the new one uses (same ID) and leaves the others dormant.
- `build_plan` classifies each entry's node as active, dropped (it or its closest existing ancestor is dormant) or missing. Entries on dropped nodes are returned in `ignored` with `"dropped": true`, and the UI removes them without the "no longer match" notice.
- Merges are applied in a loop with `_drop_unused_inputs_of_merged`, since dropping an absorbed node's inputs can drop nodes other merges refer to. When a merge target is dropped, its remaining sources merge into the first of them; those entries carry `"replacement"`, which the UI writes into the plan.
- Nodes carry `is_alternate`.
- Saved plans with old-style IDs from before this change (`...__<recipe>>Screws`) lose the adjustments below a switch, with the usual notice.

## Tests
- `tests/unit/test_graph_state.py`: shared inputs keep their node and override; unused inputs are dropped with their adjustments reported as dropped; shared inputs are rescaled.
- `tests/unit/test_merges.py`: switching merged Screws to Cast Screws leaves no Iron Rod behind, the new Iron Ingot input is sized for the whole group, and every item stays balanced. Adhered Iron Plate (no Screws) drops the absorbed branch's Screws.
- `tests/unit/test_api.py`: a merged input dropped by a switch leaves the rest of the merge, a dropped merge target hands the group to the next member, entries from older plans aren't marked dropped, `is_alternate`.
- `tests/integration/test_ui.py`: "(A)" label, switching a merged node leaves no old inputs and shows no notice, switching away and back starts a fresh branch.
