# 059 — Make something from a by-product

**Type:** feature · **Priority:** P2 · **Status:** Open · **Related:** [058](done/058-burn-fuel-byproducts.md), [057](done/057-supply-driven-power.md), [031](done/031-byproducts-as-supply.md), [040](done/040-chain-tab.md)

## Goal
Turn what's left of a by-product into something useful, sized by the by-product itself. Example: Rocket Fuel from 300 Crude Oil leaves 150 Polymer Resin a minute from its Fuel Refineries. Residual Plastic (resin 60 + water 20 → 20 Plastic) turns it into 50 Plastic a minute, to be used by another plan through the Chain tab, or at least sunk as Plastic.

Today a by-product can only cover demand in its own plan (031) or go to the Sink. In a limited plan (057), the demand rows have to be fuels only, so a Plastic demand row to take the resin isn't even possible.

This is supply-driven planning for one branch, limited to by-products (what a by-product is: see 058). The maker's own rate sets the branch's size, so nothing has to decide which side drives the graph.

## Rule
- On a by-product, **Make from it**: pick a recipe that takes the item. Polymer Resin has Residual Plastic, Residual Rubber and Polyester Fabric. The plan adds a branch of that recipe, sized to what's left of the by-product after its uses (Use as Supply first, as for burning and the Sink).
- The branch's other ingredients (e.g. the water) are made or mined as usual, with every adjustment nodes get: clocks, recipe switches for those inputs, merges, Built marks, notes. Its node ids are stable, keyed by the maker and the by-product.
- **One step only.** The branch's output goes to the **Sink** or becomes a **supply** for the Chain tab (a circle like a demand target). Fluids can't be sunk, so they're a supply. Anything made further from it belongs in another plan, through the Chain tab. The branch's own by-products follow the usual rules (use, burn as in 058, Sink), but nothing more is made from them.
- **Limited plans:** the branch grows with the plan, so 057's probe accounts for it: an inbound row the branch uses still limits the plan.

## By-product choices per node and item
- A node can have several by-products, so each choice is per node and item: Use as Supply / Sink / Burn for Power (058) / Make from it (recipe, and to the Sink or a supply). E.g. `byproducts: {"<node>|Polymer Resin": {"choice": "make", "recipe": "Residual Plastic", "to": "supply"}}`.
- A plan saved with per-node choices (`{"<node>": "use"}`) still loads: the choice applies to each of the node's by-products.

## The Chain tab
- The Chain tab is drawn from the saved plans, without the server, but a branch's output rate comes from the calculation. So **the plan saves its last calculated supplies**: each Make from it output sent to the Chain, with its rate. This is the first calculated number saved in a plan. A tab's numbers are as of its last calculation; any change to the plan recalculates it anyway.
- A limited plan still gives the Chain tab no fuel (it burns it), but it does give its by-product supplies.

## UI
- The by-product panel: **Make from it** with a list of the recipes that take the item (none: back to the Sink, or to burning for a fuel), and where the output goes (Sink / Chain supply).
- The graph: the branch's nodes, and its output as a supply circle (or an edge to the Sink).
- The user guide: a section on Make from it, with the resin example.

## Out of scope
- Several steps of processing in one plan.
- A recipe taking two by-products at once (e.g. a by-product of one node and another of a second node).
