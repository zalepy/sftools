# 024 — By-products go to a Sink node

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** 030, [031](031-byproducts-as-supply.md)

> **Done (2026-10-13).** `FactoryGraph._sink_node` adds a node `sink` with every shown node's by-products (`sink.inputs`: from, item, rate, fluid) and the fluids among them (`sink.fluids`). The graph draws it round, with dotted edges from each maker; fluid edges are red, and the Sink gets a thick red border when it holds any. Its panel shows the totals per item, its power and which fluids can't be sunk, without recipe, clock or split controls. AWESOME Sink count: one per 1200 solids/min (a Mk.6 belt) until 028; power 30 MW each. Tests: unit (inputs, fluids, count and power, no Sink without by-products, by-products follow clocks) and browser (shape, red border, edge classes, panel).

## Problem
When a node's recipe has a by-product, `Recipe.generate_demands` emits it as a SINK demand, which `calculate_demands` then drops. The by-product isn't shown anywhere, so the user doesn't see that it has to go somewhere: in the game, an unused by-product blocks the building.

## Decisions (2026-10-13)
- **One Sink node** per plan, round. Every node's by-product output goes to it on an edge with the item and rate. Nothing else changes: building counts stay as they are.
- **Fluids** (item categories LIQUIDS and GAS) can't be sunk in the game. They still connect to the Sink, as a placeholder so the rest of the plan calculates, but the Sink then gets a **big red border** (and the fluid edges are red): the user has to deal with them by hand.
- The Sink counts **power** (AWESOME Sink: 30 MW each; not in the scraped data). **No sink points**: points are a stop-gap, plans shouldn't be built on them.
- By-products used as supply are [031](031-byproducts-as-supply.md); this ticket only shows them.

## Prior art: the planning spreadsheet
The spreadsheet's `biproduct` column subtracts by-products from demand (`max(…, 0)`), so any by-product beyond the demand disappears without a trace. Its formulas are circular (each row's by-product sum includes rows that depend on it), so the live sheet must have iterative calculation on: it settles when the feedback is small, and stops at the iteration limit without a warning otherwise. No chain in the workbook has a loop in the numbers today (checked 2026-10-13).
