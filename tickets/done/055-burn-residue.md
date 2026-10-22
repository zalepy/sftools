# 055 — Burn Heavy Oil Residue for power

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** [024](024-byproducts-to-sink.md), [031](031-byproducts-as-supply.md), [047](047-fit-last-clock.md)

## Goal
Heavy Oil Residue (a fluid by-product of Plastic, Rubber and others) can't be sunk, so it went to the Sink as a red placeholder. In the game it's refined into Fuel and burned in Fuel Generators. The plan does that instead: the Refineries and Generators the residue needs, and the power they make.

## Decisions (agreed with the user, 2026-10-23)
- **Not supply-driven planning:** a fixed two-step chain sized from the residue left over, not a general "fill this supply" mode.
- **Ratios:** Residual Fuel turns 60 residue into 40 Fuel per minute per Refinery. A Fuel Generator makes 250 MW from 20 Fuel per minute (750 MJ each). So per 30 residue/min: one Generator and half a Refinery.
- **Residue left over is burned, by default:** what isn't used as supply goes to the burn chain, not the Sink. The by-product's "Send to Sink" button reads "Burn for Power" for residue; it's the same choice (`sink`), as the Sink can't take fluids anyway.
- **The Refinery is a normal node** (id `burn`): its own clocks, fit-clock, Built count and logistics. It always runs Residual Fuel (no recipe switch, move branch or merge).
- **The Generators are a node like the Sink** (id `generators`): no output, no clocks. ⌈Fuel / 20⌉ Generators at 100%. When the residue changes (more or less Plastic), the count follows; no clock to readjust. The last ones are underfed: they burn with gaps, which has the same overall effect.
- **Power is the real average:** Fuel/min × 12.5 MW, not count × 250 MW. E.g. 100 residue/min: 66.67 Fuel/min, 2 Refineries, 4 Generators (3.33 fed), 833 MW.
- **Kept separate from other Fuel demand:** the burned Fuel doesn't cover Fuel the plan needs elsewhere. Using residue elsewhere is what "Use as Supply" does.
- **Logistics:** pipes into the Refinery and into the Generators, like any other edge; the Generators have an input side.
- The Fuel Generator isn't in the scraped data: its 250 MW and 20 Fuel/min are constants, like the Sink's.

## Notes
- Implemented 2026-10-23: `domain/models/residue.py` (the burn Refinery, node `burn`, sized after the rest of the plan), `graph_view.generators_node` (node `generators`). The residue burned is a use of the by-product (`used: {"burn": rate}`), so the edges, pipes and logistics come from the existing code; the Generators get an input side only.
- The Refinery can't switch recipe, move its branch or merge (the panel hides those; the graph won't merge it).
- Tests: `tests/unit/test_residue.py`, `tests/integration/test_residue.py`, and `generatorsText` in `tests/js/node-info.test.mjs`.
