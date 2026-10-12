# 027 — "Optimize branch" with preview

**Type:** feature · **Priority:** P3 · **Status:** Open · **Depends on:** 023, 026 · **Related:** 028

## Goal
The tool computes optimizations only when asked, on a part of the plan the user picks, and shows them before anything changes.

## Design sketch
- Start from a node: **Optimize…**, choose:
  - **goal:** fewest buildings, least power, exact match (no surplus), fewest power shards; later "fits belt Mk N" (028);
  - **scope:** this node, or the branch below it to some depth.
- Clocks the user has set are left alone unless included explicitly.
- The result is a **preview**, not a change: per node, before → after for buildings, clocks, power, shards and surplus, each with a checkbox. Applying adds the checked changes to the plan as ordinary clock settings, which the user can edit, and one undo step (026) reverts them.
- Consequences the tool can't see (layout, belts, physical space) are why every change can be rejected or undone.

## Questions
- Goals beyond these, and how to combine two (e.g. fewest buildings, then least power)?
