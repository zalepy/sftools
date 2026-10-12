# 030 — Inbound production

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** 018, 024

> **Done (2026-10-12).** Asked for after 018's "Supplied from outside": define supplies in the side panel, next to the demand targets, and use them when the graph is calculated.

## Behaviour
- **Inbound Production** rows under Demand Targets: item and rate, applied with Calculate, saved and exported with the plan (`inbound: [{item, rate}]`), part of undo/redo.
- In `FactoryGraph.recalculate`, top down (Kahn order), each node or merge group of the item takes what it needs from what is left, and its buildings cover only the rest. The first consumers reached get it first, so shallow nodes are covered before deep ones.
- A node left with nothing to make is hidden with everything under it that then needs nothing (`FactoryGraph.unused`). Its merges, clocks and recipes stay in the plan and apply again when the inbound rate is lowered.
- Each inbound item is shown as a node `inbound:<item>` (sky-blue border, "used of available"), with edges to the consumers it feeds. It can't be merged, split, clocked or switched.
- Nodes switched to "Supplied from outside" don't take inbound production.

## Possible follow-ups
- Choose which nodes get the inbound production first (today: top down).
- 024 (by-products as supply) can reuse the same pool, with the by-product rate as the inbound rate.
