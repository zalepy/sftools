# 062 — Merged nodes: inbound and by-products cover their consumers top down

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** [030](030-inbound-production.md), [031](031-byproducts-as-supply.md), [021](021-node-splitting.md)

> **Done (2026-11-02).** `cover` in `FactoryGraph.recalculate` (`domain/models/factory_graph.py`) takes the consumers in `position` order (where the top-down queue reached them; the user's demand first) and covers each fully before the next. Tests: `tests/unit/test_cover_order.py` (fail on the proportional share: 1.2/1.8, and 57.14 of the rods' 100).

## Goal
Inbound production and by-products cover demand top down between nodes (030, 031), but inside a merged node they were shared among the node's consumers in proportion to what each asks. Example (RAD book, 2026-11-02): the Ficsonium Fuel Rods make 100 Dark Matter Residue a minute; Ficsonium needs 200 and Dark Matter Crystal 150, from one merged residue node. The rods' residue was split 57.14 / 42.86, so it couldn't all go to Ficsonium; unmerging the node was the only way.

## Rule
- When inbound production or a by-product covers a merged node, it goes to the node's consumers **top down**: the user's demand first, then the consumers in the plan's top-down order (the order nodes are calculated in: a node before the nodes under it). Each consumer is covered fully before the next gets any. In the example: Ficsonium gets all 100, Dark Matter Crystal none, and the residue node makes the rest.
- Totals don't change: what the node makes is the same. Only which edges carry the inbound or the by-product, and so the logistics (belts, pipes), change.
- Same for inbound and by-products (they share one rule). Saved plans with merged nodes covered by inbound production may show different edges after this.

## Tests
- Unit: a merged node covered in part by a by-product, and by inbound production: the top consumer gets it first; totals as before.
- The RAD case: the rods' residue all goes to Ficsonium with the residue nodes merged.
