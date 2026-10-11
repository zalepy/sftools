# 008 — Recipe switch deactivates nodes that are shared through merges

**Type:** bug · **Priority:** P1 · **Status:** Open

## Problem
`set_subtree_dormancy` walks `node.children` in the merged graph. If a child was merged into a target that other parents also use, switching one parent's recipe deactivates the shared target and its whole subtree.

Reactivation (`expand_new_subtree` → `set_subtree_dormancy(False)`) also brings back the whole old subtree, including descendants whose recipe was switched later. Their stale old children come back too.

## Fix
- [ ] Decide dormancy from the starting (unmerged) structure plus each node's current recipe, not from the merged links
- [ ] A node is dormant only if **all** of its unmerged parents are dormant or no longer need its item
- [ ] Tests: recipe switch with a shared merged child; switching A→B→A on nested nodes
