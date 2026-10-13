# 032 — Solve by-product loops on request

**Type:** feature · **Priority:** P3 · **Status:** Open · **Related:** [031](done/031-byproducts-as-supply.md)

## Goal
A by-product use that would feed a node above its own maker is left out today (031): it goes to the Sink on an amber "(loop)" edge. Let the user ask for it to be solved.

## Sketch (agreed 2026-10-13)
- "Solve" on the loop's edge, stored in the plan (e.g. `byproducts: {node_id: "solve"}`).
- Iterate like the spreadsheet does: recalculate with the by-product amounts of the previous round, until they change by less than a threshold, up to a cap (Sheets: 50). Say so if it didn't settle (whole buildings can make it flip between two states).
- Rare in practice: the only loops in the game data need an item made as another recipe's by-product (e.g. Water from the Battery recipe).
