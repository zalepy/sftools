# Expanded Demands Calculation Algorithm

This document outlines the approach used to calculate the expanded demands given the root demands.

## High-Level Approach

The algorithm uses a breadth-first expansion strategy to determine the total production requirements. It starts with a set of "root demands" and iteratively resolves them into "sub-demands" until all demand chains reach their base raw resources (leaf nodes).

## Algorithm Steps (Initial Expansion)

The initial graph is built using a breadth-first expansion strategy:

1.  **Iterative Expansion**: The algorithm runs for a fixed depth (default 10) to expand demand chains layer by layer.
2.  **Recipe Selection**: `default_recipe_for(item)` picks a recipe that makes the item: not unpackaging, main product before by-product, then basic → converter → alternate. If an item reappears in its own chain, it is treated as an input instead of being expanded again.
3.  **Graph Construction**: For each demand, it creates a `ProductionNode` and generates sub-demands for its ingredients.
4.  **FactoryGraph Generation**: The resulting structure is encapsulated in a `FactoryGraph` object, which manages the master list of all nodes and their initial topology.

## Factory Management (Stateful Backend)

The `FactoryGraph` class serves as the stateful orchestrator for the production chain.

### 1. Master Graph vs. UI Representation
- **Master Graph**: Stores every `ProductionNode` ever created for the current demand set, including those that are currently "absorbed" (merged) or dormant.
- **UI Representation**: `graph_view.ui_nodes(graph)` generates a reduced version of the graph for the frontend. It aggregates values for merged groups and maps relationships (parents/children) to their respective "representative" nodes.

### 2. Stateful Merging
- **`apply_merge(source, target)`**: Non-destructively merges two nodes.
    - It marks the source node as `absorbed_by` the target and moves its parent/child links to the target (used for the UI view).
    - Each node keeps its own external demand; the group's demand is computed in `recalculate`.
    - The source node is preserved in the master graph.
    - **Meaning:** the merged nodes are built together in the game, as one shared set of buildings. Each branch keeps its own inputs, sized to that branch's share (see below). Merging is used to:
        - consolidate fractional counts (two lines at x.5 buildings each become a whole number),
        - set one clock speed for the whole set,
        - reduce clutter in a big graph.
    - Merging nodes that run different recipes is allowed (the merged node runs the target's recipe). The UI shows a brief message when it happens.

## Propagation Algorithm (Recalculation)

The `recalculate` method updates the throughput and building counts across the graph whenever clocks change or nodes are merged. It works on the *unmerged* structure (each node's original parent and children), with merge groups on top:

1.  **Groups**: every running node belongs to a group, either its merge target (following chains of merges) or itself. Absorbed nodes don't run on their own (scale 0).
2.  **Order**: groups are processed top-down (Kahn's algorithm) over the edges `group(original parent) -> group(node)`.
3.  **Demand per member**: for each member of a group, its demand is
    - its external demand (root nodes), plus
    - its share of what its original parent's group needs of its item. The parent group's need for an item is split between the input nodes for that item under the group's members, in proportion to each member's share of the group's demand. Members without an input node for the item (e.g. the group runs a different recipe) leave their share to the members that have one. The parts of a split input node divide their parent's share equally.
4.  **Scale**: a group's demand is the sum of its members' demands. Its target's buildings come from that demand and the target's clocks: fixed groups (e.g. the last building at 200%) plus as many buildings at the node's clock as the rest needs, rounded up. `building_scale` is the sum of the buildings' clocks, and the inputs scale with it. In exact mode (`build_plan(exact=True)`, tests only) the scale is the exact demand / output rate.
5.  **Power**: each building draws `base power × clock^1.321928` (`CLOCK_POWER_EXPONENT`), and needs one power shard per 50% above 100%.

So with 2/min Smart Plating and 2/min Modular Frame, merging their two Reinforced Iron Plate nodes gives one plate line at 5/min (2 + 3). The Smart Plating branch's Screws node supplies 2/5 of that line's Screws, and the Modular Frame branch's supplies 3/5. Every item is made exactly as fast as it is consumed (`tests/unit/test_merges.py`).
