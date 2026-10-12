# 027 — "Optimize branch" with preview

**Type:** feature · **Priority:** P3 · **Status:** Parked · **Depends on:** 023, 026 · **Related:** 028

## Goal
The tool computes optimizations only when asked, on a part of the plan the user picks, and shows them before anything changes.

## Design sketch
- Start from a node: **Optimize…**, choose:
  - **goal:** fewest buildings, least power, exact match (no surplus), fewest power shards; later "fits belt Mk N" (028);
  - **scope:** this node, or the branch below it to some depth.
- Clocks the user has set are left alone unless included explicitly.
- The result is a **preview**, not a change: per node, before → after for buildings, clocks, power, shards and surplus, each with a checkbox. Applying adds the checked changes to the plan as ordinary clock settings, which the user can edit, and one undo step ([026](done/026-undo-redo.md)) reverts them.
- Consequences the tool can't see (layout, belts, physical space) are why every change can be rejected or undone.

## Proposed breakdown (agreed, parked 2026-10-12)
1. **Goals** for a first version:
   - **Exact match:** clocks set so output equals demand with no surplus (e.g. 8×100% + 1×37.5%).
   - **Least power:** more buildings at lower clocks; power grows faster than output (clock^1.32), so underclocking saves power.
   - **Fewest buildings:** overclock with power shards, up to 250% (up to 3 shards per building).
   - "Fewest shards" is left out: it is exact match without overclocking.
2. **Combining goals:** one main goal, ties settled in a fixed order (fewest buildings → least power → fewest shards) rather than a user-ranked list.
3. **Limits:** a cap on buildings per node for least power (it would otherwise keep adding buildings at lower clocks); clocks in steps the game accepts (0.1% or whole percent).
4. **Scope:** "this node" or "this node and everything below it", no depth setting at first.
