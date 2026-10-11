# Plan: Node Splitting for Logistical Control

## Goal
Allow users to split a single `ProductionNode` into two or more separate nodes. This is useful for logistics (e.g., splitting production across two separate floor areas) and for running buildings at specific manual clock speeds even when a single building is sufficient for demand.

## Technical Strategy

### 1. Identity & Addressing
Currently, `node_id` is derived from the "parent path" (`parent_path__RecipeName`). To allow multiple nodes for the same path, we must introduce a unique suffix or "Instance Index".
- **Proposed ID Format**: `parent_path__RecipeName[instance_id]`
- **Impact**: The `calculate_demands` logic will need to check a "Split Map" to see if it should generate multiple nodes instead of a single one.

### 2. Instruction Persistence
Splits should be stored in the persistent state (similar to `merges` and `overrides`).
- **Data Structure**: `splits: { "original_node_id": { "count": 2, "ratios": [0.5, 0.5] } }`
- **Location**: Add to the plan state: `PlanRequest` in `src/sftools/api/schemas.py`, replayed in `build_plan`, and `localStorage` in `index.html`.

### 3. Calculator Logic (demand_calculator.py)
In `calculate_demands`, when processing a demand:
1. Check if the target `node_id` exists in `splits`.
2. If so, create N nodes.
3. Distribute the incoming demand across the split nodes (by default 50/50, or using stored ratios).
4. For children of a split node: the split node behaves like any other parent.

### 4. Merging vs. Splitting
- **Conflict Resolution**: If a user drags two "split" nodes together, the system should treat this as a request to remove the Split instruction for those specific entities.
- **Priority**: Manual Merges should generally take precedence over split logic during the "Flattening" phase.

---

## ⚠️ Re-evaluation Required Before Implementation

Before picking this up, the developer MUST evaluate how the following recent additions/changes impact the design:

1. **Recipe Switching**: If a feature to change recipes on a per-node basis is implemented, the Split logic must ensure that a split node can have a different recipe than its sibling, OR that the Split instruction is tied to the *path* regardless of the recipe.
2. **Current `parent_demands` Logic**: Review the recent UI addition that breaks down inputs by parent. Splitting is fundamentally a way to "clean up" this breakdown by moving demands into separate boxes.
3. **Circular Dependencies**: Ensure that splitting a node in a potential feedback loop (if those are ever supported) doesn't cause the topological sort or recalculation to hang.
4. **Override Persistence**: Verify how `user_scale` (manual overrides) should be distributed when a node is split. Should both nodes inherit the override? Or should it be cleared/halved?

## UI Requirements
- A **"Split"** button in the Selected Node panel (visible even for single-parent nodes).
- Visual feedback on the graph for split nodes (perhaps a specific edge style or icon).
