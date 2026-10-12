# 020 — Merging two nodes double-counts their inputs

**Type:** bug · **Priority:** P0 · **Status:** Open · **Related:** 015

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
