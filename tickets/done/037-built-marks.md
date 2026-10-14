# 037 — Mark buildings as built

**Type:** feature · **Priority:** P3 · **Status:** Done

> **Done (2026-10-14).** The selected node has a "Built" box (how many of its buildings are built in the game), "of N" and an All Built / Not Built button; Clear Built Marks clears the plan's marks. Done nodes fade (opacity) and get a green check at the top left; partly built ones show "6/8", and more than needed shows the check and "10/8". The plan stores `built: {node id: {count, recipe}}` (saved, exported, undoable; browser only, not sent to the server). Needed = whole buildings with clocks, else the scale rounded up; nodes without buildings (inbound, supplied from outside) have no mark. A mark made for another recipe doesn't count; the panel says so. Both modes; production nodes only in logistics mode. Browser tests: `test_marking_buildings_built` in both UI test files.

## Request
Mark buildings as "done", as in the spreadsheet, in both modes.

## Decisions (2026-10-14)
- Record the number of buildings built, not a flag: when the plan grows, the node shows "6/8" and no longer counts as done.
- Done nodes are dimmed with a check; partly built shows just "6/8".
- Logistics mode: production nodes only, not the logistics nodes.
