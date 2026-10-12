# 024 — By-products count as supply

**Type:** feature · **Priority:** P2 · **Status:** Open

## Problem
When a node's recipe has a by-product, `Recipe.generate_demands` emits it as a SINK demand, which `calculate_demands` then drops. So the by-product never reduces a demand for the same item elsewhere in the plan. For example, the Fuel recipe makes Polymer Resin as a by-product, but a Plastic line in the same plan still builds its own Polymer Resin production in full. The by-product also isn't shown on the node, so the user doesn't see that it has to go somewhere (in the game, an unused by-product blocks the building).

## Prior art: the planning spreadsheet
The author's spreadsheet has a `biproduct` column per item: the sum of what other rows make of it as a by-product. That sum is subtracted from the item's demand: `target = max(demand + goal − supplied − by-product, 0)`. Each chain is merged by item (one row per item), so this is a single sum. A "blocker" note in the sheet's readme covers the opposite case: a by-product nothing uses has to be consumed or sunk.

## Design questions
- **Which demands get the by-product?** In the sftools tree, an item can have many nodes. Options:
  - (a) A plan-wide pool per item: by-product output is shared out over that item's nodes in proportion to their demand.
  - (b) Only nodes the user links, like a merge: drag the by-product onto a node to feed it.
  - (c) Show by-products on the node and in a plan summary only, without changing any demand.

  (c) is the cheap first step; (a) is closest to the spreadsheet.
- **Order:** a by-product's amount depends on its node's scale, which depends on demand. (a) creates feedback loops, e.g. resin by-product → less resin production → … The calculation must stay acyclic or iterate to a fixed point.
- **Unused by-products:** show them, e.g. as a "to sink" total per item, since in the game they block production.
