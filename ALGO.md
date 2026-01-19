# Expanded Demands Calculation Algorithm

This document outlines the approach used to calculate the expanded demands given the root demands.

## High-Level Approach

The algorithm uses a breadth-first expansion strategy to determine the total production requirements. It starts with a set of "root demands" and iteratively resolves them into "sub-demands" until all demand chains reach their base raw resources (leaf nodes).

## Algorithm Steps

The process executes in a loop (currently set to a fixed depth of 10 iterations) to expand the demand tree layer by layer.

For each iteration:

1.  **Process Current Layer Demands**: Iterate through the list of demands waiting to be resolved.
2.  **Determine Recipe**:
    *   For each demand item, the algorithm looks for a **Default/Basic** recipe.
    *   *Note: Alternate recipes are currently filtered out.*
    *   If no basic recipe is found, the item is considered a "leaf" node (e.g., Raw Ore), and no further sub-demands are generated for it.
3.  **Calculate Scale (Buildings Needed)**:
    *   The required rate is compared to the recipe's standard output rate.
    *   `Scaler = Demand Rate / Recipe Output Rate`
    *   If `ROUND_UP_SCALER_FLAG` is enabled, the scaler is rounded up to the nearest integer (simulating a full building count).
4.  **Generate Production Node**:
    *   A production node is created representing the buildings required.
    *   **Power Calculation**: `Total Power = Base Building Power * Scaler`
5.  **Generate Sub-Demands**:
    *   The "Source" demand is converted into "Sub" demands based on the recipe's ingredients.
    *   For each ingredient: `Ingredient Rate = Base Ingredient Rate * Scaler`
6.  **Recursion / Loop**:
    *   The newly generated sub-demands become the input for the next iteration.
    *   This continues until the recursion depth is hit or no new PROD demands are generated.
7.  **Aggregation**:
    *   At the end of each step, the new production nodes and sub-demands are aggregated into the final totals.

## Computational Details

### Rate Calculation
Rates are calculated linearly based on the scaler.
- **Demand Rate**: The amount of item required per minute.
- **Scaler**: `ceil(Demand Rate / Base Recipe Output)` (if rounding is on).
- **Ingredient Demand**: `Base Recipe Ingredient Rate * Scaler`.

### Power Calculation
Power consumption is derived from the building type associated with the chosen recipe.
- **Power Usage**: `Building Base Power * Number of Buildings (Effective Scaler)`.
- *Note: Some buildings may have variable power definitions (like particle accelerators), which are handled during the building load phase.*

## Interactive Recalculation

Once the graph is constructed, the user can apply overrides to specific nodes via the UI.

### 1. Scale Properties
`ProductionNode` maintains two scale properties:
- **`original_building_scale`**: The computed requirement based on its parents' throughput.
- **`user_scale`**: An optional override set by the user. If `None`, the computation falls back to `original_building_scale`.
- **`building_scale` (Effective)**: `user_scale ?? original_building_scale`.

### 2. Propagation Algorithm
The `recalculate_graph` method propagates changes top-down (from consumers to producers) using a **Topological Sort** (Kahn's Algorithm):

1.  **Initialize In-Degrees**: Count how many parent nodes each node has.
2.  **Queue Roots**: Add nodes with zero in-degree (direct demands/graph roots) to the processing queue.
3.  **Process and Propagate**:
    *   For each node in the queue, its effective `building_scale` determines its current `scaled_inputs`.
    *   For each child of the current node, update its `original_building_scale` by summing the input requirements from **all** its parents.
    *   Decrement the in-degree of the children. If a child's in-degree reaches zero, add it to the queue.
4.  **Result**: The entire graph's throughput and power stats are updated to reflect the overrides while maintaining the architectural integrity of the production chain.
