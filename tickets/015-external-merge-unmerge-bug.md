# 015 — Wrong state after merging and unmerging external-demand nodes

**Type:** bug · **Priority:** P1 · **Branch:** `distinct_extrenal_demand` (commit "added but fails after unmerge") · **Status:** Re-check

> **Update (2026-10-11):** With the stateless API, unmerge replays the plan without that merge, so the unmerge half of this bug may be gone. Merging still moves external demand onto the target. Re-test on master.

From `scratch.txt`:
- Merging an external node with a non-external node marks the result as external. It should stay non-external.
- Repro: merge two non-external nodes (A←B), then merge external node E into them, then unmerge:
  - E shows scale 0
  - one non-external node is marked external and has picked up E's demand
- When E is merged into the already-merged node, unmerging restores E correctly, but A and B come back still merged.

Likely causes:
- `apply_merge` moves `parent_demands["External Demand"]` onto the target. `_rebuild_structure` doesn't move it back, because `_reset_structure` doesn't restore `parent_demands`.
- `remove_merge(target_id)` removes every merge into that target, not just the selected one.

## Tasks
- [ ] Keep each node's own external demand separate from the merged group's total (calculate the total in `recalculate`/`get_ui_data` instead of changing the source node)
- [ ] Unmerge removes one constituent, not every merge into the target
- [ ] Turn the scenarios above into tests
