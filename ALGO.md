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
- **UI Representation**: The `get_ui_data()` method generates a reduced version of the graph for the frontend. It aggregates values for merged groups and maps relationships (parents/children) to their respective "representative" nodes.

### 2. Stateful Merging
- **`apply_merge(source, target)`**: Non-destructively merges two nodes.
    - It transfers `External Demand` and all parent/child links to the target.
    - It marks the source node as `absorbed_by` the target.
    - The source node is effectively "orphaned" but preserved in the master graph.
- **`remove_merge(source_id)`**: Rebuilds the graph structure from the captured initial topology plus the remaining active merges. This allows for instant "unmerging" without a full backend recalculation.

## Propagation Algorithm (Recalculation)

The `recalculate` method updates the throughput and building counts across the graph whenever an override is changed or nodes are merged.

1.  **Initialize In-Degrees**: Count parent relationships for each node based on the *current* manipulated structure.
2.  **Identify Roots**: Find nodes with zero in-degree (Top-level demands or orphaned nodes).
3.  **Root Scale Reset**: 
    - For each root node, update its scale based ONLY on its `External Demand`. 
    - Nodes orphaned by merges (no parents) naturally drop to 0 scale during this step.
4.  **Topological Sort (Kahn's Algorithm)**:
    - Iterate through the graph top-down.
    - For each node, its effective `building_scale` determines its current `scaled_inputs`.
    - Sum the required input rates from **all** parents and update the child's `original_building_scale`.
    - Decrement children's in-degrees and add to the queue when they reach zero.
5.  **Handling Overrides**:
    - If a node has a `user_scale` override, that value is used for `building_scale` and drives all downstream requirements.
    - Overrides for merged groups are applied to the "Representative" (target) node.
