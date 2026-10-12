# 026 — Undo and redo of plan changes

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** 027

> **Done (2026-10-12).** `static/js/history.js` keeps up to 50 plan snapshots, as JSON strings, for the page session. `save()`, which runs after every successful change, records a step when the plan changed. Undo/redo load a snapshot into the form and state and recalculate it, and the selected node stays selected if it still exists. Demand edits (applied with Calculate) and imports are steps too, which answers the question below. ↶ ↷ buttons sit in the header, so they work with the side panel hidden. Ctrl+Z, Ctrl+Y and Ctrl+Shift+Z work except in text fields, where they edit the text. A new change after an undo drops the steps that could have been redone. Not done: keeping the history across reloads (sessionStorage). Browser tests: undo/redo of a merge, keyboard shortcuts (and not while typing), a new change dropping redo.

## Goal
Step back through plan changes: a merge, split, recipe switch, clock change, demand edit, or an applied optimization (027). This is the safety net that makes optimizations worth trying, and useful on its own.

## Design sketch
- The plan is a small JSON snapshot (demands, recipes, merges, splits, clocks), and the server is stateless, so undo means: keep a history of snapshots and recalculate an earlier one.
- Record a snapshot after each successful change. Undo/redo buttons in the panel, plus Ctrl+Z / Ctrl+Y (Ctrl+Shift+Z) when focus isn't in a text field.
- History lives in the page, so a reload clears it. Keeping it across reloads (sessionStorage) is optional.
- A cap, e.g. 50 steps.

## Questions
- Should demand-row edits be undo steps, or only graph changes?
