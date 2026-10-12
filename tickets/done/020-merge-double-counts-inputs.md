# 020 — Merging two nodes double-counts their inputs

**Type:** bug · **Priority:** P0 · **Status:** Done · **Related:** 015

> **Fixed (2026-10-12):** option 2, as decided: the merged node is shared, and each branch keeps its own inputs, sized to its share.
> - `FactoryGraph.recalculate` now works from the unmerged structure (each node's original parent and children), with merge groups on top (see ALGO.md).
> - A group's demand is the sum of its members' demands. For each input item, the group's need is split between the members' input nodes in proportion to each member's share. Members without an input node for that item leave their share to those that have one (e.g. the merged node runs Adhered Iron Plate, which needs Rubber that only its own branch has).
> - External demand is no longer moved onto the merge target. Each node keeps its own (`ProductionNode.external_demand`), which may also help with 015.
> - `test_reported_bug_copper_ingots` had locked in the inflation ("THIS IS THE N:M INFLATION": both Wire nodes asserted at 21). It now asserts the split (21 x 4/5.5 and 21 x 1.5/5.5).
> - **What merging is for** (from the user, 2026-10-12): the nodes are built together in the game. It consolidates fractional building counts, allows one scale factor (overclock) for the whole set, and reduces clutter.
> - Merging nodes with different recipes stays allowed. The UI shows a brief non-blocking message (top-left of the graph, about 4 s) naming both recipes and the one the merged node runs.
> - **Tests:** `tests/unit/test_merges.py` checks that every item is made exactly as fast as it is consumed (with `round_up=False`). It covers same-recipe merges, a merged node running another recipe, a missing input on the absorbed branch, merged roots, chained merges at every level, and up to 40 pairwise merges per plan in three plans.

## Problem
Found 2026-10-12 while adding the derivation view. When node B is merged into node A, `apply_merge` moves B's input nodes (B's children) under A, but A keeps its own input nodes as well. In `FactoryGraph.recalculate`, each input node sums its parents' scaled inputs for its item. Both A's Screws node and B's Screws node now have A as a parent, so **each** takes A's *full* Screws demand, and every input is produced twice.

Repro: 2/min Smart Plating + 2/min Modular Frame, merge the two Reinforced Iron Plate nodes (`round_up=False`):

| | Screws made / needed | Iron Plate made / needed |
|---|---|---|
| No merge | 110 / 110 | 30 / 30 |
| Merged | 170 / 110 | 60 / 30 |
| Merged, then target switched to Bolted | 216.67 / 133.33 | 60 / 30 |

This happens on `master` too, so it isn't caused by the node-ID change (016). The original stateful backend (#13) already had it. The sidebar's **Children** list of a merged node shows the duplicate input nodes. If the merged node runs a different recipe from the absorbed one, the absorbed node's old-recipe inputs (e.g. default-recipe Iron Plate under a Bolted target) are also kept and fed.

## Options
1. **Merge the inputs too:** when B is absorbed into A, absorb each of B's input nodes into A's input node for the same item, recursively. Inputs with no counterpart under A (A runs a different recipe) are dropped from the merged group. This matches what a merge means physically: one factory for both.
2. **Split the demand:** keep B's input nodes, but have each input node take only its share of A's demand. This needs a per-child share, which the model doesn't have.

Option 1 fits the existing model (it reuses `apply_merge`) and keeps "merge" meaning "build this once".

## Tasks
- [ ] Decide between the options (1 recommended)
- [ ] Test: made == needed for every item after merging two nodes with the same recipe, and after merging into a node running a different recipe
- [ ] Check what this means for 015 (merge/unmerge oddities with external demand may be the same root cause)
