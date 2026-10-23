# 056 — Reference layouts: crude oil to Turbofuel power

**Type:** feature · **Priority:** P3 · **Status:** Open · **Related:** [049](done/049-user-guide.md)

## Goal
A worked example to build from: a fixed layout that turns 1350 Crude Oil/min into Turbofuel and burns it for power, drawn as a schematic in the app. It replaces the color-coded cells of the user's spreadsheet (C26:V56). It isn't a plan: nothing is calculated from the user's input.

## The layout
| Step | Buildings | In | Out |
|---|---|---|---|
| Crude → Fuel | 20 Refineries at 100% + 3 at 83.334% | 1350 Crude Oil/min (from the top, pipes not drawn) | 900 Fuel/min (green pipe 500, yellow 400) + 675 Polymer Resin/min |
| Fuel → Turbofuel | 40 Refineries at 100% (22 on green, 18 on yellow) | 900 Fuel/min + 600 Compacted Coal/min (from the bottom) | 750 Turbofuel/min (red pipes, 4 ends) |
| Turbofuel → power | 100 Fuel Generators, 25 per red pipe end | 750 Turbofuel/min (7.5 each, 2,000 MJ) | 25,000 MW |
| Resin | Sunk, for the purpose of the layout | 675/min on 2 Mk.4 belts | |

- Crude → Fuel: 3 Refineries at the top (33.33 Fuel/min each), then two columns of 10. The left column (1–5, 11–15) feeds the green pipe, which starts at the top three's 100 and adds 40 per Refinery to 500; the right column (6–10, 16–20) feeds the yellow pipe, to 400. The pipes run side by side between the columns.
- The resin runs on two parallel belts on the floor under the green and yellow pipes, which are raised right above them, and turns off vertically about where the yellow pipe splits sideways.
- Fuel → Turbofuel: the green pipe runs down the middle and along the bottom; the yellow pipe goes round the outside. They meet at the bottom corners (Refineries 11 and 22). The red Turbofuel pipes run between the Refinery columns.
- The Generators are 4 floors below, with a footprint matching the Refineries above; each red pipe end dives down to its group.

## Decisions (agreed with the user, 2026-10-23)
- **A fixed reference, not a plan:** no tabs, no calculation, no Built marks. The numbers are set upfront, as the user worked them out; only a game update would change them.
- **A schematic, not to scale:** buildings as boxes (numbered, with their clock where it isn't 100%), pipes and belts as traces in their item colors, with the running totals along each pipe. Belts on the floor are drawn under the pipes (dashed, offset), which conveys "pipes raised above" without 3D.
- **The Generators are a note,** not drawn: how many, where (4 floors down, under each red pipe end), what they make.
- **A table** of the numbers next to the drawing (the one above).
- **Described as data, drawn as SVG:** the layout is a data file (buildings, traces, labels, note, table); a renderer draws it. Hovering a building or a trace says what it is and carries.
- **Checked against the game data** by a unit test: each pipe's totals add up from the buildings feeding it, at the recipes' rates and clocks, and each fits its pipe tier (500 Fuel/min on a Mk.2 pipe, 600). A game update that changes a recipe fails a test instead of leaving the layout quietly wrong.
- **In the app:** a Layouts button in the header, next to Guide and Legend, opening a drawer if the drawing fits its width, a page otherwise. Opening it closes the Guide and the Legend, and the other way round.
- **One layout for now,** but the data format and the panel leave room for a library later (a list of layouts, each its own data file).

## Tasks
1. The data format and this layout's file, from the spreadsheet.
2. The renderer: a pure module turning the data into SVG (unit-tested in `tests/js/`), and the panel around it.
3. The unit test of the numbers against the game data.
4. The header button and drawer (or page); browser tests that it opens, draws, and closes the Guide and Legend.
5. A section in the user guide pointing to it.
