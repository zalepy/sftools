import json
import os.path
import math
from typing import Optional, Dict, Tuple, List, Set

from sftools_service.config.default import NAME_TO_BUILDING_CATEGORY_MAP, NAME_TO_ITEM_CATEGORY_MAP
from sftools_service.domain.enums.demand_type import DemandType
from sftools_service.domain.enums.recipe_type import RecipeType
from sftools_service.domain.models.building import Building
from sftools_service.domain.models.demand import Demand
from sftools_service.domain.models.item import Item
from sftools_service.domain.models.production_node import ProductionNode
from sftools_service.domain.models.recipe import Recipe


DATA_PATH = 'data'


def get_int_or_none(data_dict, key, strippings) -> Optional[int]:
    value_as_str = data_dict.get(key)
    if not value_as_str:
        return None
    try:
        value = int(value_as_str.strip(strippings).replace(',', ''))
    except (ValueError, AttributeError) as ex:
        print('failed converting', key, ': >' + value_as_str + '< to int')
        value = None

    return value


def get_float_or_none(data_dict, key, strippings) -> Optional[float]:
    value_as_str = data_dict.get(key)
    if not value_as_str:
        return None
    try:
        value = float(value_as_str.strip(strippings).replace(',', ''))
    except (ValueError, AttributeError) as ex:
        print('failed converting', key, ': >' + value_as_str + '< to int')
        value = None

    return value


def load_buildings(path: str) -> Dict[str, Building]:
    with open(os.path.join(path, 'buildings.json'), 'rt') as f:
        buildings_json = json.load(f)

    buildings_by_name = {}
    
    for entry in buildings_json:
        name = entry.get('name')
        category = NAME_TO_BUILDING_CATEGORY_MAP.get(entry.get('Category'))

        power = 0
        power_used = entry.get('Power used')
        if power_used:
            try:
                power = - int(power_used.strip('MW').replace(',', ''))
            except (ValueError, TypeError) as ex:
                print('failed converting power', power_used, ' to int')
                power = 0
        power_used_plutonium = entry.get('Power used (Plutonium Pellet)')
        power_used_nuclear = entry.get('Power used (Nuclear Pasta)')
        if power_used_nuclear:
            power = -1500

        power_generated = entry.get('Power generated')
        if power_generated:
            try:
                power = int(power_generated.strip('MW').replace(',', ''))
            except (ValueError, TypeError) as ex:
                print('failed converting power', power_generated, ' to int')
                power = 0
        power_impure = entry.get('Power generated (MAP\\Impure)')
        power_normal = entry.get('Power generated (MAP\\Normal)')
        power_pure = entry.get('Power generated (MAP\\Pure)')
        if power_impure:
            power = 50

        width = get_int_or_none(entry, 'Width', 'm')
        length = get_int_or_none(entry, 'Length', 'm')
        height = get_int_or_none(entry, 'Height', 'm')
        input = get_int_or_none(entry, 'Input', '')
        output = get_int_or_none(entry, 'Output', '')

        building = Building(name, category, power, width, length, height, input, output)
        buildings_by_name[name] = building

    return buildings_by_name


def load_items(path: str, buildings: Dict[str, Building]) -> Tuple[Dict[str, Item], Dict[str, Recipe]]:
    with open(os.path.join(path, 'items.json'), 'rt') as f:
        items_json = json.load(f)
    items_models = {}
    recipe_models = {}
    item_recipe_json_by_name = {}
    # items_json = big_items_json[0]
    for entry in items_json:
        item_name = entry.get('name')
        # print('>>> processing', item_name)
        category = NAME_TO_ITEM_CATEGORY_MAP.get(entry.get('Category'))
        stack = get_int_or_none(entry, 'Stack size', '')
        energy = entry.get('Energy')
        if energy:
            try:
                energy = float(energy.strip('MJ').replace(',', ''))
            except TypeError as ex:
                print('Failed to convert energy', energy, 'to float')
                energy = None
        sink_points = get_int_or_none(entry, 'Resource Sink Points', '')
        recipes_json = entry.get('recipes')

        new_item = Item(item_name, category, stack, sink_points, [])
        item_recipe_json_by_name[item_name] = (new_item, recipes_json)

    for item_name, item_recipes_json_tuple in item_recipe_json_by_name.items():
        item, recipes_json = item_recipes_json_tuple
        if recipes_json:
            for recipe_name, recipe_details in recipes_json.items():
                building_name = recipe_details.get('building')  # "Manufacturer",
                ingredient1_rate = get_float_or_none(recipe_details, 'ingredient1_rate', ' /minÂ³')
                ingredient1_stack = get_int_or_none(recipe_details, 'ingredient1_stack', ' /minÂ³.')
                ingredient1_name = recipe_details.get('ingredient1_name')  # "Encased Uranium Cell",
                ingredient1_item = None
                if item_recipe_json_by_name.get(ingredient1_name):
                    ingredient1_item = item_recipe_json_by_name.get(ingredient1_name)[0]
                
                # ... ingredients 2,3,4 ...
                ingredient2_rate = get_float_or_none(recipe_details, 'ingredient2_rate', ' /minÂ³')
                ingredient2_stack = get_int_or_none(recipe_details, 'ingredient2_stack', ' /minÂ³.')
                ingredient2_name = recipe_details.get('ingredient2_name')
                ingredient2_item = None
                if item_recipe_json_by_name.get(ingredient2_name):
                    ingredient2_item = item_recipe_json_by_name.get(ingredient2_name)[0]
                    
                ingredient3_rate = get_float_or_none(recipe_details, 'ingredient3_rate', ' /minÂ³')
                ingredient3_stack = get_int_or_none(recipe_details, 'ingredient3_stack', ' /minÂ³.')
                ingredient3_name = recipe_details.get('ingredient3_name')
                ingredient3_item = None
                if item_recipe_json_by_name.get(ingredient3_name):
                    ingredient3_item = item_recipe_json_by_name.get(ingredient3_name)[0]
                    
                ingredient4_rate = get_float_or_none(recipe_details, 'ingredient4_rate', ' /minÂ³')
                ingredient4_stack = get_int_or_none(recipe_details, 'ingredient4_stack', ' /minÂ³.')
                ingredient4_name = recipe_details.get('ingredient4_name')
                ingredient4_item = None
                if item_recipe_json_by_name.get(ingredient4_name):
                    ingredient4_item = item_recipe_json_by_name.get(ingredient4_name)[0]
                    
                output1_rate = get_float_or_none(recipe_details, 'output1_rate', ' /minÂ³')
                output1_stack = get_int_or_none(recipe_details, 'output1_stack', ' /minÂ³.')
                output1_name = recipe_details.get('output1_name')  # "Uranium Fuel Rod",
                output2_rate = get_float_or_none(recipe_details, 'output2_rate', ' /minÂ³')
                output2_stack = get_int_or_none(recipe_details, 'output2_stack', ' /minÂ³.')
                output2_name = recipe_details.get('output2_name')  # "Heavy Oil Residue"

                output1_item = None
                if item_recipe_json_by_name.get(output1_name):
                    output1_item = item_recipe_json_by_name.get(output1_name)[0]

                output2_item = None
                if item_recipe_json_by_name.get(output2_name):
                    output2_item = item_recipe_json_by_name.get(output2_name)[0]

                if building_name == 'Converter':
                    recipe_type = RecipeType.CONVERSION
                elif recipe_name.count('Alternate'):
                    recipe_type = RecipeType.ALTERNATE
                else:
                    recipe_type = RecipeType.BASIC

                recipe = Recipe(
                    recipe_name,
                    buildings.get(building_name),
                    output1_item,
                    output1_rate,
                    output1_stack,
                    output2_item=output2_item,
                    output2_rate=output2_rate,
                    output2_stack=output2_stack,
                    ingredient1_item=ingredient1_item,
                    ingredient1_rate=ingredient1_rate,
                    ingredient1_stack=ingredient1_stack,
                    ingredient2_item=ingredient2_item,
                    ingredient2_rate=ingredient2_rate,
                    ingredient2_stack=ingredient2_stack,
                    ingredient3_item=ingredient3_item,
                    ingredient3_rate=ingredient3_rate,
                    ingredient3_stack=ingredient3_stack,
                    ingredient4_item=ingredient4_item,
                    ingredient4_rate=ingredient4_rate,
                    ingredient4_stack=ingredient4_stack,
                    recipe_type=recipe_type
                )

                recipe_models[recipe_name] = recipe
                item.add_recipe(recipe)

        items_models[item.name] = item

    return items_models, recipe_models


def load_models(path: str):
    buildings = load_buildings(path)
    items, recipes = load_items(path, buildings)

    return items, recipes, buildings


from sftools_service.domain.models.factory_graph import FactoryGraph


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
        # Format: parent_path__Relationship__RecipeName because one parent might need same item for multiple things?
        # Actually simplest is: parent_path / OutputItem
        # But recipes produce items.
        # Let's use: parent_path__RecipeName
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


def recalculate_graph(graph: FactoryGraph, overrides: Optional[Dict[str, float]] = None, round_up: bool = False):
    """
    Recalculates the scales of nodes based on user overrides and parent requirements.
    This is now a wrapper around FactoryGraph.recalculate.
    """
    graph.recalculate(overrides, round_up)
    return graph

# Keep main for simple testing if needed
def main():
    data = load_models(DATA_PATH)
    items, recipes, buildings = data
    root_demand_item = items['Smart Plating']
    root = Demand('Smart Plating', root_demand_item, 2.0, DemandType.PRODUCE)
    
    graph = calculate_demands(items, [root], round_up=True)
    for nid, node in graph.all_nodes.items():
        print(f"{nid}: {node}")

if __name__ == "__main__":
    main()
