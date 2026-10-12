# 026 — Undo and redo of plan changes

**Type:** feature · **Priority:** P2 · **Status:** Open · **Related:** 027

## Goal
Step back through plan changes: a merge, split, recipe switch, clock change, demand edit, or an applied optimization (027). This is the safety net that makes optimizations worth trying, and useful on its own.

## Design sketch
- The plan is a small JSON snapshot (demands, recipes, merges, splits, clocks), and the server is stateless, so undo means: keep a history of snapshots and recalculate an earlier one.
- Record a snapshot after each successful change. Undo/redo buttons in the panel, plus Ctrl+Z / Ctrl+Y (Ctrl+Shift+Z) when focus isn't in a text field.
- History lives in the page, so a reload clears it. Keeping it across reloads (sessionStorage) is optional.
- A cap, e.g. 50 steps.

## Questions
- Should demand-row edits be undo steps, or only graph changes?
