# 021 — Node splitting

**Type:** feature · **Priority:** P3 · **Status:** Done · **Related:** 016, 018, 020

> **Update:** Splitting was removed with simple mode on 2026-10-17 (logistics mode never had it); it's on the branch `backup/simple-mode`.

> **Done (2026-10-12).** Replaces `SPLIT_PLAN.md`. Decisions from the user: equal parts only for now; merged nodes can't be split; Split/Set Parts and Unsplit buttons in the node panel, with the part number on the graph.

## Goal
Split one `ProductionNode` into two or more nodes, e.g. to build them in different places, or to run each part at its own clock speed.

## Design
- **Plan entry:** `splits: {"<node_id>": k}` (k ≥ 2), saved and exported with the plan like merges and overrides.
- **Parts:** a node split into k parts is k nodes, each with an equal share (1/k) of the node's demand. Part 1 keeps the node's ID, so its existing override, recipe switch and merges stay with it. The other parts are `<id>~2`, `<id>~3`, ... (`#n` already means "second demand row for the same item").
- **Each part has its own inputs:** `…Reinforced Iron Plate~2__Screws`, and so on down the tree. Splits apply as nodes are created (`split_parts` in `calculate_demands` and `expand_new_subtree`), so they also work below a recipe switch.
- **Each part is an ordinary node:** its own override (the "clock speed" use), its own recipe switch, and it can be merged. Dragging one part onto another merges them, which puts them back on one set of buildings.
- **Merged parents:** in `FactoryGraph.recalculate`, the parts of a split input divide their parent's share of the group's need equally.
- **Merged nodes can't be split:** which branch's demand would go to which part? The panel disables Split and says to unmerge first.
- **Stale entries:** a split with fewer than 2 parts, or for a node not in the plan, is reported in `ignored` with kind `"split"`. Splits on inactive branches are kept silently, like the other entries. (Superseded by 022: entries on dropped inputs are now discarded.)
- **Fewer parts / Unsplit:** the UI drops the overrides, recipes, merges and splits that belonged to removed parts (the part's ID, its inputs `__…` and its own parts `~…`).
- **UI:** "Split Into Parts" (number + Split; Set Parts on a split node) and "Unsplit Node" in the node panel; split nodes are labelled `[part/count]` on the graph. Nodes carry `split: {of, part, count}` (or `null`).

## Not done (possible follow-ups)
- Unequal shares (e.g. 70/30). The plan format could take a list of shares instead of a count. Until then, adjust a part's buildings with its override.
- Splitting a merged node.

## Tests
- `tests/unit/test_splits.py`: equal parts with their own inputs, totals unchanged, rounding per part, a part's own recipe, splits below a recipe switch, per-part overrides, merging parts back, split inputs of a merged node, serialization, stale and invalid entries, and every node of a plan split in two stays balanced.
- `tests/unit/test_api.py`: splits are replayed and serialized; too few parts are reported.
- `tests/integration/test_ui.py`: split, set parts (dropping a removed part's override), unsplit; merged nodes can't be split; dragging a part onto another merges them.
