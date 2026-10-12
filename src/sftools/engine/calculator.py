import math
from typing import Dict, List, Optional, Tuple

from sftools.domain.enums.demand_type import DemandType
from sftools.domain.enums.recipe_type import RecipeType
from sftools.domain.models.demand import Demand
from sftools.domain.models.factory_graph import FactoryGraph
from sftools.domain.models.item import Item
from sftools.domain.models.production_node import ProductionNode
from sftools.domain.models.recipe import Recipe


RECIPE_TYPE_ORDER = {RecipeType.BASIC: 0, RecipeType.CONVERSION: 1, RecipeType.ALTERNATE: 2}


def default_recipe_for(item: Item) -> Optional[Recipe]:
    """
    The recipe used for a demand of `item` until the user switches it. In order of preference:
    1. not unpackaging (Unpackage X needs Packaged X, which is made from X)
    2. item as main product before by-product (by-product chains such as
       Compacted Coal <- Ionized Fuel <- Rocket Fuel <- Turbofuel <- Compacted Coal loop back)
    3. basic, then converter, then alternate recipes
    4. the recipe named after the item, then the order in the game data
    """
    def rank(indexed):
        index, recipe = indexed
        return (
            recipe.name.startswith('Unpackage'),
            not recipe.is_main_product(item.name),
            RECIPE_TYPE_ORDER[recipe.type],
            recipe.name != item.name,
            index,
        )

    candidates = [(i, r) for i, r in enumerate(item.recipes) if r.produces(item.name) and r.rate_of(item.name)]
    if not candidates:
        return None
    return min(candidates, key=rank)[1]


def root_node_ids(item_names: List[str]) -> List[str]:
    """Root nodes are keyed by item; a repeated item gets '#2', '#3', ... in order."""
    seen: Dict[str, int] = {}
    ids = []
    for name in item_names:
        seen[name] = seen.get(name, 0) + 1
        ids.append(name if seen[name] == 1 else f"{name}#{seen[name]}")
    return ids


def child_node_id(parent: ProductionNode, item_name: str, items_map: Dict) -> str:
    """
    '<parent id>__<item>'. When the parent runs a recipe other than its default, the recipe is part
    of the child's ID ('<parent id>__<recipe>><item>'), so each recipe gets its own input nodes:
    adjustments made under one recipe stay with it and come back when the parent is switched back.
    """
    if parent.recipe is not None and parent.recipe is not default_recipe_for(items_map[parent.output_item_name]):
        return f"{parent.id}__{parent.recipe.name}>{item_name}"
    return f"{parent.id}__{item_name}"


def split_parts(node_id: str, rate: float, splits: Optional[Dict[str, int]]) -> List[Tuple[str, float]]:
    """
    (node id, rate) for each part of a node: a node split into k parts is k nodes with an equal share
    of its demand. Part 1 keeps the node's ID, so its adjustments stay; the others are '<id>~2', '<id>~3', ...
    """
    count = (splits or {}).get(node_id, 1)
    if count < 2:
        return [(node_id, rate)]
    return [(node_id if part == 1 else f"{node_id}~{part}", rate / count) for part in range(1, count + 1)]


def calculate_demands(items_map, root_demands_list: List[Demand], scale_overrides: Dict[str, float] = None, round_up: bool = True,
                      splits: Optional[Dict[str, int]] = None) -> FactoryGraph:
    if scale_overrides is None:
        scale_overrides = {}

    graph = FactoryGraph()

    # Queue: (Demand, NodeId, ParentNode, items produced by the ancestors)
    # ParentNode is None for roots
    queue: List[Tuple[Demand, str, Optional[ProductionNode], frozenset]] = []

    root_ids = root_node_ids([d.item.name for d in root_demands_list])
    for d, root_id in zip(root_demands_list, root_ids):
        queue.append((d, root_id, None, frozenset()))

    processed_count = 0
    max_nodes = 5000 # Safety brake

    while queue and processed_count < max_nodes:
        current_demand, node_id, parent_node, ancestors = queue.pop(0)

        if current_demand.type == DemandType.SINK:
            # Sinks are terminal for this logic, we don't produce them
            continue
        if current_demand.item.name in ancestors:
            # The item is already being made further up this chain; treat it as an input
            continue

        item = items_map.get(current_demand.item.name)
        if not item or not item.recipes:
            continue

        recipe = default_recipe_for(item)
        if recipe is None:
            continue

        for part_id, target_rate in split_parts(node_id, current_demand.rate, splits):
            # Calculate Base Scaler from demand rate
            base_scaler = target_rate / recipe.rate_of(item.name)

            # Apply rounding (only for initial generation when no override exists)
            if part_id in scale_overrides:
                # Use the scale override directly - this is the building multiplier
                scaler = scale_overrides[part_id]
            elif round_up:
                # Round up to next integer for buildings
                scaler = math.ceil(base_scaler - 0.00001) # epsilon for float precision
                if scaler == 0 and base_scaler > 0: scaler = 1 # Safety
            else:
                scaler = base_scaler

            # Create Node
            node = recipe.generate_production_node(part_id, scaler, item.name)
            node.ideal_building_scale = base_scaler

            # Track where demand came from
            if parent_node:
                node.parent_demands[parent_node.id] = target_rate
            else:
                node.parent_demands["External Demand"] = target_rate
                node.external_demand = target_rate

            graph.add_node(node)

            # Link Graph
            if parent_node:
                graph.link(parent_node, node)

            # Enqueue Sub-Demands for the recipe
            for sd in recipe.generate_demands(scaler, item.name):
                queue.append((sd, child_node_id(node, sd.item.name, items_map), node, ancestors | {item.name}))

            processed_count += 1

    return graph


def _ancestor_items(node: ProductionNode) -> frozenset:
    """Items produced by `node` and the nodes above it in the original tree (node IDs are paths)."""
    items = set()
    current = node
    while current is not None:
        items.add(current.output_item_name)
        current = next((p for p in current.parents if current.id.startswith(p.id + '__')), None)
    return frozenset(items)


def expand_new_subtree(graph: FactoryGraph, parent_node: ProductionNode, items_map: Dict, round_up: bool = True,
                       splits: Optional[Dict[str, int]] = None):
    """
    Expands a new subtree from an existing node that just had its recipe changed.
    Checks for existing dormant nodes before creating new ones.
    """
    if not parent_node.recipe:
        return

    # Queue of (Demand, ParentNodePath, ParentNode)
    # We start with the sub-demands of the parent_node
    queue = []
    ancestors = _ancestor_items(parent_node)
    # Use effective scale for initial sub-demands
    sub_demands = parent_node.recipe.generate_demands(parent_node.building_scale, parent_node.output_item_name)
    for sd in sub_demands:
        queue.append((sd, child_node_id(parent_node, sd.item.name, items_map), parent_node, ancestors))

    processed_count = 0
    max_nodes = 1000 # Smaller brake for subtree

    while queue and processed_count < max_nodes:
        current_demand, node_id, p_node, ancestors = queue.pop(0)

        if current_demand.type == DemandType.SINK:
            continue
        if current_demand.item.name in ancestors:
            continue

        item = items_map.get(current_demand.item.name)
        if not item or not item.recipes:
            continue

        recipe = default_recipe_for(item)
        if recipe is None:
            continue

        for part_id, target_rate in split_parts(node_id, current_demand.rate, splits):
            # Check if node already exists
            existing_node = graph.get_node(part_id)
            if existing_node:
                # Re-activate it and its subtree
                graph.set_subtree_dormancy(part_id, False)
                # Update demand from parent
                existing_node.parent_demands[p_node.id] = target_rate
                # Ensure link exists (though it should if it was a child before)
                graph.link(p_node, existing_node)
                continue

            # Create New Node
            base_scaler = target_rate / recipe.rate_of(item.name)
            scaler = math.ceil(base_scaler - 0.00001) if round_up else base_scaler
            if round_up and scaler == 0 and base_scaler > 0: scaler = 1

            node = recipe.generate_production_node(part_id, scaler, item.name)
            node.recipe = recipe
            node.ideal_building_scale = base_scaler
            node.parent_demands[p_node.id] = target_rate

            graph.add_node(node)
            graph.link(p_node, node)

            # Recurse
            for sd in recipe.generate_demands(scaler, item.name):
                queue.append((sd, child_node_id(node, sd.item.name, items_map), node, ancestors | {item.name}))

            processed_count += 1


def recalculate_graph(graph: FactoryGraph, overrides: Optional[Dict[str, float]] = None, round_up: bool = False):
    """
    Recalculates the scales of nodes based on user overrides and parent requirements.
    This is now a wrapper around FactoryGraph.recalculate.
    """
    graph.recalculate(overrides, round_up)
    return graph

def switch_recipe_in_graph(graph: FactoryGraph, node_id: str, new_recipe: Recipe, items_map: Dict, round_up: bool = True,
                           splits: Optional[Dict[str, int]] = None):
    """
    Switches the recipe for a node, proactively deactivating its current subtree
    and activating/expanding the new one.
    """
    node = graph.get_node(node_id)
    if not node:
        return

    # 1. Deactivate old subtree
    # Important: only deactivate children, not the node itself
    for child in list(node.children):
        graph.set_subtree_dormancy(child.id, True)

    # 2. Swap Recipe
    node.update_from_recipe(new_recipe)
    node.is_dormant = False # Ensure it's active

    # 3. Activate/Expand New Subtree
    expand_new_subtree(graph, node, items_map, round_up, splits)

    # 4. Recalculate everything
    graph.recalculate(round_up=round_up)


def _on_inactive_branch(graph: FactoryGraph, node_id: str, items_map: Dict) -> bool:
    """
    A missing node whose closest existing ancestor now runs a different recipe than the one in the ID
    (see child_node_id) was created under that ancestor's other recipe: the entry is not stale, it
    applies again if the user switches the ancestor back.
    """
    end = len(node_id)
    while (end := node_id.rfind('__', 0, end)) != -1:
        ancestor = graph.get_node(node_id[:end])
        if ancestor is None:
            continue
        segment = node_id[end + 2:].split('__', 1)[0]
        recipe_name, marker, _ = segment.rpartition('>')
        if not marker:
            default = default_recipe_for(items_map[ancestor.output_item_name])
            recipe_name = default.name if default else None
        return ancestor.recipe is not None and ancestor.recipe.name != recipe_name
    return False


def build_plan(
    items_map: Dict,
    recipes_map: Dict[str, Recipe],
    demands: List[Tuple[str, float]],
    round_up: bool = True,
    recipes: Optional[Dict[str, str]] = None,
    merges: Optional[Dict[str, str]] = None,
    overrides: Optional[Dict[str, float]] = None,
    splits: Optional[Dict[str, int]] = None,
) -> FactoryGraph:
    """
    Builds a FactoryGraph from the full plan description.
    The API is stateless: every request replays demands (with splits) -> recipe switches -> merges -> overrides.
    Splits apply as nodes are created (see split_parts), so the parts of a split node, and their
    inputs, exist before any other entry refers to them.

    Entries that can't apply are skipped and listed in `graph.ignored` as
    {"kind": "recipe" | "merge" | "override" | "split", "node_id", "reason"}. Entries for dormant nodes or
    inactive branches are skipped silently, since they apply again if an upstream recipe is switched back.
    """
    ignored = []
    splits = dict(splits or {})
    for node_id, count in list(splits.items()):
        if count < 2:
            ignored.append({"kind": "split", "node_id": node_id, "reason": f"needs at least 2 parts, got {count}"})
            del splits[node_id]

    root_demands = [Demand(name, items_map[name], rate, DemandType.PRODUCE) for name, rate in demands]
    graph = calculate_demands(items_map, root_demands, round_up=round_up, splits=splits)

    def missing(node_id: str) -> bool:
        return graph.get_node(node_id) is None and not _on_inactive_branch(graph, node_id, items_map)

    # Parents first: a child's ID extends its parent's ID, so shorter IDs are switched first.
    for node_id, recipe_name in sorted((recipes or {}).items(), key=lambda kv: len(kv[0])):
        node = graph.get_node(node_id)
        recipe = recipes_map.get(recipe_name)
        if node is None:
            if missing(node_id):
                ignored.append({"kind": "recipe", "node_id": node_id, "reason": "node not in plan"})
            continue
        if recipe is None:
            ignored.append({"kind": "recipe", "node_id": node_id, "reason": f"unknown recipe {recipe_name!r}"})
            continue
        if not recipe.produces(node.output_item_name):
            ignored.append({"kind": "recipe", "node_id": node_id,
                            "reason": f"{recipe_name!r} does not produce {node.output_item_name}"})
            continue
        if node.is_dormant or node.recipe is recipe:
            continue
        switch_recipe_in_graph(graph, node_id, recipe, items_map, round_up=round_up, splits=splits)

    for node_id in list(splits):
        if missing(node_id):
            ignored.append({"kind": "split", "node_id": node_id, "reason": "node not in plan"})
            del splits[node_id]

    for source_id, target_id in (merges or {}).items():
        stale = [n for n in (source_id, target_id) if missing(n)]
        if stale:
            ignored.append({"kind": "merge", "node_id": source_id, "reason": f"node not in plan: {', '.join(stale)}"})
            continue
        graph.apply_merge(source_id, target_id)

    for node_id in overrides or {}:
        if missing(node_id):
            ignored.append({"kind": "override", "node_id": node_id, "reason": "node not in plan"})

    graph.recalculate(overrides or {}, round_up=round_up)
    graph.ignored = ignored
    graph.splits = splits
    return graph
