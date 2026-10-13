# 028 — Belt and pipe capacity

**Type:** feature · **Priority:** P3 · **Status:** Open · **Depends on:** [033](033-logistics-mode.md) · **Related:** 023, 027

## Problem
Belt logistics affect planning but aren't covered. A line can exceed what its belt tier carries, and some splits are awkward to build balanced: a split into 5, for example, doesn't come from plain 2- and 3-way splitters. These shape decisions such as clocking a node down to fit a belt.

## Ideas
- Belt and pipe tier per plan (maybe per edge), and a warning on edges that carry more than that tier can.
- Show how a node's buildings divide its input: which splits are simple (2, 3, 4, 6, 8, 9, …) and which need extra work (5, 7, …).
- A "fits belt Mk N" goal for optimize branch (027).

Scope (2026-10-13): part of the logistics mode ([033](033-logistics-mode.md)), not the simple mode, which stays without belts. The ideas above are its first step; the producer/consumer planning in 033 builds on them.

## Questions
- Tiers per plan or per edge? Is a split warning useful, or just noise?
