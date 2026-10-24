# 058 — Burn fuel by-products for power

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** [055](055-burn-residue.md), [057](057-supply-driven-power.md), [031](031-byproducts-as-supply.md), [059](../059-make-from-a-byproduct.md)

## Goal
A fuel left over as a by-product is burned in its generators instead of going to the Sink. Example: Rocket Fuel by Nitro Rocket Fuel from 300 Crude Oil (a limited plan, 057) sends 50 Compacted Coal a minute to the Sink. It should feed 7 Coal Generators (525 MW). Today the only workaround is a second demand row for Compacted Coal at the right ratio (50 to 300, worked out by hand). That leaves a demanded Compacted Coal node at 0/min, as the by-product covers all of it.

The plan is for an optimum: nobody sinks a fuel on purpose, except perhaps for a while, until the generators' water is routed in.

## What a by-product is
A by-product belongs to a node, not to a recipe. Each node is there to make one item: what its consumer, or the demand row, asks for. The recipe's other outputs are the node's by-products (`recipe.other_outputs(node.output_item_name)`, as in 031 and 055). The same recipe can play either role: a node running Fuel for Polymer Resin (e.g. under Polyester Fabric) has Fuel as its by-product, while a node running Fuel for Fuel has the resin. The user sets the intent by what they demand, so nothing is guessed.

## Rule
- **What's left** of a fuel by-product after its uses (Use as Supply, 031) goes to its generators (`power.GENERATORS`), in every plan, limited or not. A node's main item is never burned.
- **Solid fuels** (Coal, Compacted Coal, Petroleum Coke, the fuel rods): burned by default. **Send to Sink** stays a choice, recorded in the plan; the button then reads **Burn for Power**. Today's default Sink isn't recorded, so saved plans burn these from their next calculation; a Sink the user chose (recorded `sink`) stays.
- **Fluid fuels** (Fuel, Liquid Biofuel, Turbofuel, Rocket Fuel, Ionized Fuel): always burned, as they can't be sunk. No Sink choice, like Heavy Oil Residue.
- Heavy Oil Residue is unchanged: it isn't a fuel itself, so it goes through the Residual Fuel Refinery (055), whose Fuel joins the Fuel Generators.

## Generators
- The burned by-product is recorded as a use of it by its generators (`used: {<generators id>: rate}`), as the residue is by the burn Refinery, so the Sink gets nothing of it. The graph draws an edge from the maker to the generators, and the generators' logistics input side gets it as an entry.
- It joins the generators' node of its kind (`power.generator_nodes`), counted per fuel with the demanded fuels and the residue's Fuel. In a plan that isn't limited, the generators appear for burned by-products alone, as the Fuel Generators do for residue now.
- **Water:** Coal Generators and Nuclear Power Plants burning a by-product need water, which is only known once the plan is calculated. One more pass: calculate, read what's burned, then calculate again with Water roots for all the generators (057's `with_water`, extended). Burning doesn't change the by-products, so two passes settle it. In a limited plan, the probe does the same, so a Water inbound row still limits correctly.
- In a limited plan, the summary's power includes these generators.

## Smaller fixes
- In a limited plan, a demanded fuel that by-products cover entirely isn't shown at 0/min: its generators replace the demand circle, so there's nothing to show.

## UI
- The by-product panel: for a solid fuel, the toggle reads **Send to Sink** / **Burn for Power**, with a hint that sinking makes sense only for a while (e.g. until the water is routed in). For a fluid fuel, no Sink button, as for residue.
- The user guide (By-products and the Sink; Power from a supply) says fuel by-products are burned, and that saved plans change.

## Notes
- The choice stays per node here (`byproducts: {node: use|sink|solve}`); 059 makes it per node and item.

## Built
- The choice `burn` ("don't use as supply, burn what's left") is recorded when the user picks Burn for Power, so it's kept like the others; the toggle of a used fuel by-product reads Burn for Power and sets it.
- The 0/min node is left out only when no building makes it and by-products cover all of it (inbound production covering it still shows it, with its edge).
