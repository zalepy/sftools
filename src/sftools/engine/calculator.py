import math
from typing import Dict, List, Optional, Tuple

from sftools.domain.enums.demand_type import DemandType
from sftools.domain.enums.recipe_type import RecipeType
from sftools.domain.models.demand import Demand
from sftools.domain.models.factory_graph import FactoryGraph
from sftools.domain.models.production_node import ProductionNode
from sftools.domain.models.recipe import Recipe


def calculate_demands(items_map, root_demands_list: List[Demand], scale_overrides: Dict[str, float] = None, round_up: bool = True) -> FactoryGraph:
    if scale_overrides is None:
        scale_overrides = {}

    graph = FactoryGraph()
    
    # Queue: (Demand, ParentNodePath, ParentNode)
    # ParentNode can be None for root
    queue: List[Tuple[Demand, str, Optional[ProductionNode]]] = []
    
    for d in root_demands_list:
        queue.append((d, "root", None))

    processed_count = 0
    max_nodes = 5000 # Safety brake

    while queue and processed_count < max_nodes:
        current_demand, parent_path, parent_node = queue.pop(0)
        
        if current_demand.type == DemandType.SINK:
            # Sinks are terminal for this logic, we don't produce them
            continue

        item = items_map.get(current_demand.item.name)
        if not item or not item.recipes:
            continue
            
        # Select Recipe (Default / Basic)
        non_alt_recipes = [r for r in item.recipes if r.type == RecipeType.BASIC]
        if not non_alt_recipes:
            continue
        recipe = non_alt_recipes[0] # Pick first basic recipe

        # Determine Node ID
        # Format: parent_path__[r]ParentRecipeName__RecipeName
        # For root nodes, parent_path is "root" and there is no ParentRecipeName
        if parent_node and parent_node.recipe:
            node_id = f"{parent_path}__[r]{parent_node.recipe.name}__{recipe.name}"
        else:
            node_id = f"{parent_path}__{recipe.name}"
        
        # Calculate Base Scaler from demand rate
        target_rate = current_demand.rate
        base_scaler = target_rate / recipe.output_rate
        
        # Apply rounding (only for initial generation when no override exists)
        if node_id in scale_overrides:
            # Use the scale override directly - this is the building multiplier
            scaler = scale_overrides[node_id]
        elif round_up:
            # Round up to next integer for buildings
            scaler = math.ceil(base_scaler - 0.00001) # epsilon for float precision
            if scaler == 0 and base_scaler > 0: scaler = 1 # Safety
        else:
            scaler = base_scaler

        # Create Node
        node = recipe.generate_production_node(node_id, scaler)
        node.ideal_building_scale = base_scaler
        
        # Track where demand came from
        if parent_node:
            node.parent_demands[parent_node.id] = target_rate
        else:
            node.parent_demands["External Demand"] = target_rate

        graph.add_node(node)

        # Link Graph
        if parent_node:
            node.add_parent(parent_node)
            parent_node.add_child(node)
        
        # Generate Sub-Demands for the recipe
        sub_demands = recipe.generate_demands(scaler)
        
        # Enqueue Sub-Demands
        for sd in sub_demands:
            queue.append((sd, node_id, node))
            
        processed_count += 1

    # Return format
    # Previously: flattened dict of nodes, flat dict of demands
    # New: dict of nodes (by ID), logic handles structure
    # We don't really need to return "sub_demands" list separately unless UI needs it specifically, 
    # but the graph contains everything.
    # We'll return empty sub_demands list for compatibility or just the list of roots/leaves? 
    # Let's return empty list for 2nd arg as it was mostly for debug printing.
    graph.capture_initial_structure()
    return graph


def expand_new_subtree(graph: FactoryGraph, parent_node: ProductionNode, items_map: Dict, round_up: bool = True):
    """
    Expands a new subtree from an existing node that just had its recipe changed.
    Checks for existing dormant nodes before creating new ones.
    """
    if not parent_node.recipe:
        return

    # Queue of (Demand, ParentNodePath, ParentNode)
    # We start with the sub-demands of the parent_node
    queue = []
    # Use effective scale for initial sub-demands
    sub_demands = parent_node.recipe.generate_demands(parent_node.building_scale)
    for sd in sub_demands:
        queue.append((sd, parent_node.id, parent_node))

    processed_count = 0
    max_nodes = 1000 # Smaller brake for subtree

    while queue and processed_count < max_nodes:
        current_demand, parent_path, p_node = queue.pop(0)
        
        if current_demand.type == DemandType.SINK:
            continue

        item = items_map.get(current_demand.item.name)
        if not item or not item.recipes:
            continue
            
        # Select Default Recipe
        non_alt_recipes = [r for r in item.recipes if r.type == RecipeType.BASIC]
        if not non_alt_recipes:
            continue
        recipe = non_alt_recipes[0]

        # Determine Node ID using the isolated scheme
        node_id = f"{parent_path}__[r]{p_node.recipe.name}__{recipe.name}"
        
        # Check if node already exists
        existing_node = graph.get_node(node_id)
        if existing_node:
            # Re-activate it and its subtree
            graph.set_subtree_dormancy(node_id, False)
            # Update demand from parent
            existing_node.parent_demands[p_node.id] = current_demand.rate
            # Ensure link exists (though it should if it was a child before)
            p_node.add_child(existing_node)
            existing_node.add_parent(p_node)
            continue

        # Create New Node
        target_rate = current_demand.rate
        base_scaler = target_rate / recipe.output_rate
        scaler = math.ceil(base_scaler - 0.00001) if round_up else base_scaler
        if round_up and scaler == 0 and base_scaler > 0: scaler = 1

        node = recipe.generate_production_node(node_id, scaler)
        node.recipe = recipe
        node.ideal_building_scale = base_scaler
        node.parent_demands[p_node.id] = target_rate
        
        graph.add_node(node)
        p_node.add_child(node)
        node.add_parent(p_node)

        # Recurse
        for sd in recipe.generate_demands(scaler):
            queue.append((sd, node_id, node))
            
        processed_count += 1


def recalculate_graph(graph: FactoryGraph, overrides: Optional[Dict[str, float]] = None, round_up: bool = False):
    """
    Recalculates the scales of nodes based on user overrides and parent requirements.
    This is now a wrapper around FactoryGraph.recalculate.
    """
    graph.recalculate(overrides, round_up)
    return graph

def switch_recipe_in_graph(graph: FactoryGraph, node_id: str, new_recipe: Recipe, items_map: Dict, round_up: bool = True):
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
    expand_new_subtree(graph, node, items_map, round_up)

    # 4. Recalculate everything
    graph.recalculate(round_up=round_up)


def _can_switch(node: ProductionNode, recipe: Recipe) -> bool:
    # Recipes whose product can't be resolved (see tickets/004) would break recalculation.
    try:
        return bool(recipe.output_rate) and recipe.output_item.name == node.output_item_name
    except AttributeError:
        return False


def build_plan(
    items_map: Dict,
    recipes_map: Dict[str, Recipe],
    demands: List[Tuple[str, float]],
    round_up: bool = True,
    recipes: Optional[Dict[str, str]] = None,
    merges: Optional[Dict[str, str]] = None,
    overrides: Optional[Dict[str, float]] = None,
) -> FactoryGraph:
    """
    Builds a FactoryGraph from the full plan description.
    The API is stateless: every request replays demands -> recipe switches -> merges -> overrides.
    """
    root_demands = [Demand(name, items_map[name], rate, DemandType.PRODUCE) for name, rate in demands]
    graph = calculate_demands(items_map, root_demands, round_up=round_up)

    # Parents first: a child's ID extends its parent's ID, so shorter IDs are switched first.
    for node_id, recipe_name in sorted((recipes or {}).items(), key=lambda kv: len(kv[0])):
        node = graph.get_node(node_id)
        recipe = recipes_map.get(recipe_name)
        if node is None or recipe is None or node.is_dormant or node.recipe is recipe:
            continue
        if not _can_switch(node, recipe):
            continue
        switch_recipe_in_graph(graph, node_id, recipe, items_map, round_up=round_up)

    for source_id, target_id in (merges or {}).items():
        graph.apply_merge(source_id, target_id)

    graph.recalculate(overrides or {}, round_up=round_up)
    return graph
