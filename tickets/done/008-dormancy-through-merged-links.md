# 008 — Recipe switch deactivates nodes that are shared through merges

**Type:** bug · **Priority:** P1 · **Status:** Done

> **Update (2026-10-11):** Reproduced and fixed a variant. With the stateless API, recipe switches are replayed *before* merges, and each node is switched at most once from its default. So the two scenarios below (dormancy walking merged links, stale subtrees coming back) can't happen through the UI. What did happen: merge Screws B into Screws A, then switch A's parent plate to *Alternate: Adhered Iron Plate*. A goes dormant and takes B's demand with it (50 screws/min produced vs 74 needed). Fix: `FactoryGraph.apply_merge` skips a merge if either node is dormant. Regression test: `test_merge_into_node_made_dormant_by_recipe_switch`. The original scenarios are still possible in `set_subtree_dormancy` if the graph is ever edited in place again.

## Problem
`set_subtree_dormancy` walks `node.children` in the merged graph. If a child was merged into a target that other parents also use, switching one parent's recipe deactivates the shared target and its whole subtree.

Reactivation (`expand_new_subtree` → `set_subtree_dormancy(False)`) also brings back the whole old subtree, including descendants whose recipe was switched later. Their stale old children come back too.

## Fix
- [ ] Decide dormancy from the starting (unmerged) structure plus each node's current recipe, not from the merged links
- [ ] A node is dormant only if **all** of its unmerged parents are dormant or no longer need its item
- [ ] Tests: recipe switch with a shared merged child; switching A→B→A on nested nodes
