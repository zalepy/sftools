# TODO

Ideas and considerations that aren't pressing enough for a ticket. Promote an entry to `tickets/` when it's picked up.

## Planner

- **Note per node.** A free-text Note field in the node's settings (side panel, Node tab), saved with the plan, e.g. where it's built or what's left to do. Maybe a mark on the node when it has one.
- **Shard count runs outside the node box.** The clocks line ("8 × 100% + 1 × 200% · 4 shards") gets too wide for the node. Put the shard count on its own line of the label (`graph.js`, `renderGraph`).

- **Default extraction recipe.** Raw resources default to the first extraction recipe in the data: an *impure* node with a *Miner Mk.1* (30 ore/min). For example, 600 Coal/min becomes 20 miners, which overstates building counts for most real plans. Options:
  - default to a normal node with a Mk.2 miner (120/min), or a pure node with a Mk.3
  - a plan-level setting for node purity and miner tier
  - show the count as nodes needed rather than buildings

  Selection is in `default_recipe_for` (`src/sftools/engine/calculator.py`). The extraction recipes are named `<Item> (<purity>) at <Building>`.
