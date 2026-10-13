# 031 — By-products count as supply

**Type:** feature · **Priority:** P2 · **Status:** Open · **Depends on:** [024](done/024-byproducts-to-sink.md) · **Related:** 030

## Goal
A by-product covers demand for the same item elsewhere in the plan, like inbound production (030), instead of going to the Sink. E.g. Polymer Resin from the Fuel recipe reduces the Polymer Resin a Plastic line builds.

## Decisions (2026-10-13)
- **Both automatic and by hand.** The plain **Calculate** from the Demand Targets uses by-products automatically. Changes to a built graph afterwards (recipe switches, merges, splits, clocks) don't: a by-product that appears then goes to the Sink until the user chooses to use it. The tool never adjusts on its own outside Calculate.
  - Proposed: Calculate records its choices in the plan, so later recalculations replay them rather than re-deciding.
- **Per by-product choice**, made by selecting its edge: "use as supply" on an edge to the Sink, "send to Sink" on an edge to a consumer.
- **Shown** as dashed edges from the maker to the nodes it supplies. Like inbound production, nodes closest to the demands get it first; what's left goes to the Sink.
- **Loops**: a use that would feed a node upstream of its own maker is detectable exactly (add maker-before-consumer edges to the top-down order; what can't be ordered is the loop). By default it isn't applied: its edge stays on the Sink, marked as an unsolved loop. Choosing "solve" iterates like the spreadsheet does (up to a cap, with a warning if it didn't settle).

## Open
- Exactly what Calculate records (one entry per by-product node?), and how a user's later choices survive the next Calculate.
