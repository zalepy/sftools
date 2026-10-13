# 032 — Solve by-product loops on request

**Type:** feature · **Priority:** P3 · **Status:** Done · **Related:** [031](031-byproducts-as-supply.md)

> **Done (2026-10-13).** Choice `solve` per by-product node; a `solve` without a loop is a plain `use`. Found while building it: iterating like the spreadsheet, on whole buildings, settled in 1 of the 12 test cases (the 6 loops in the game data at 10 and 100/min): rounding flips the makers' building counts, and loops whose use covers more than its maker's own demand swing further each round. So `FactoryGraph.recalculate` solves on fractional buildings, halving the step whenever the difference grows (damping), then sets whole buildings in one more pass with the settled amounts; whole buildings make at least that much, the rest going to the Sink. All 12 cases settle, in 1 to 83 rounds (cap `LOOP_ROUNDS` = 100). If one doesn't, the plan is shown without the use and the panel says so. Also: a demand target covered entirely (inbound production or by-products) stays shown with no buildings, and the edge for covered demand points at it. UI: "Solve Loop" / "Stop Solving" next to "Send to Sink"; solved uses are amber dashed edges labelled "(loop, solved)". Tests: unit (solved: 4 -> 3 Blenders for 100 Water by the Battery recipe, used = 100/3; not settled -> left out; covered demand target stays shown) and browser (Solve Loop from the edge).

## Goal
A by-product use that would feed a node above its own maker is left out today (031): it goes to the Sink on an amber "(loop)" edge. Let the user ask for it to be solved.

## Sketch (agreed 2026-10-13)
- "Solve" on the loop's edge, stored in the plan (e.g. `byproducts: {node_id: "solve"}`).
- Iterate like the spreadsheet does: recalculate with the by-product amounts of the previous round, until they change by less than a threshold, up to a cap (Sheets: 50). Say so if it didn't settle (whole buildings can make it flip between two states).
- Rare in practice: the only loops in the game data need an item made as another recipe's by-product (e.g. Water from the Battery recipe).
