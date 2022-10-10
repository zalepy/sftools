import random

import networkx as nx
import matplotlib.pyplot as plt

import json
import os.path
from typing import Optional, Dict, Tuple

from sftools_service.config.default import NAME_TO_BUILDING_CATEGORY_MAP, NAME_TO_ITEM_CATEGORY_MAP
from sftools_service.domain.basic_scaler_calculator import BasicScalerCalculator
from sftools_service.domain.demand_creator import DemandCreator
from sftools_service.domain.enums.demand_type import DemandType
from sftools_service.domain.enums.item_categories import ItemCategory
from sftools_service.domain.enums.recipe_type import RecipeType
from sftools_service.domain.models.building import Building
from sftools_service.domain.models.demand import Demand
from sftools_service.domain.models.item import Item
from sftools_service.domain.models.production_node import ProductionNode
from sftools_service.domain.models.recipe import Recipe
from sftools_service.domain.production_node_creator import ProductionNodeCreator
from sftools_service.domain.recipe_selector import RecipeSelector
from sftools_service.domain.roundup_scaler_calculator import RoundupScalerCalculator

DATA_PATH = 'data'
ROUND_UP_SCALER_FLAG = True


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
        power = None
        power_used = entry.get('Power used')
        if power_used:
            try:
                power = - int(power_used.strip('MW'))
            except TypeError as ex:
                print('failed converting power', power_used, ' to int')
                power = None
        power_used_plutonium = entry.get('Power used (Plutonium Pellet)')
        power_used_nuclear = entry.get('Power used (Nuclear Pasta)')
        if power_used_nuclear:
            power = -1500

        power_generated = entry.get('Power generated')
        if power_generated:
            try:
                power = int(power_generated.strip('MW').replace(',', ''))
            except TypeError as ex:
                print('failed converting power', power_used, ' to int')
                power = None
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
                ingredient2_rate = get_float_or_none(recipe_details, 'ingredient2_rate', ' /minÂ³')
                ingredient2_stack = get_int_or_none(recipe_details, 'ingredient2_stack', ' /minÂ³.')
                ingredient2_name = recipe_details.get('ingredient2_name')  # "Electromagnetic Control Rod",
                ingredient2_item = None
                if item_recipe_json_by_name.get(ingredient2_name):
                    ingredient2_item = item_recipe_json_by_name.get(ingredient2_name)[0]
                ingredient3_rate = get_float_or_none(recipe_details, 'ingredient3_rate', ' /minÂ³')
                ingredient3_stack = get_int_or_none(recipe_details, 'ingredient3_stack', ' /minÂ³.')
                ingredient3_name = recipe_details.get('ingredient3_name')  # "Crystal Oscillator",
                ingredient3_item = None
                if item_recipe_json_by_name.get(ingredient3_name):
                    ingredient3_item = item_recipe_json_by_name.get(ingredient3_name)[0]
                ingredient4_rate = get_float_or_none(recipe_details, 'ingredient4_rate', ' /minÂ³')
                ingredient4_stack = get_int_or_none(recipe_details, 'ingredient4_stack', ' /minÂ³.')
                ingredient4_name = recipe_details.get('ingredient4_name')  # "Beacon",
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

                if output1_item:  # when output1_name is only referred inside recipes, and lacks entry in items.json
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
                    )

                    recipe_models[recipe_name] = recipe
                    item.add_recipe(recipe)

        # hack to add ore mining recipes
        if item.category == ItemCategory.ORES:
            item.add_recipe(Recipe(item.name, buildings.get('Miner Mk.1'), item, 60.0, item.stack_size))
            item.add_recipe(Recipe('Poor ' + item.name, buildings.get('Miner Mk.1'), item, 30.0, item.stack_size))
            item.add_recipe(Recipe('Rich ' + item.name, buildings.get('Miner Mk.1'), item, 120.0, item.stack_size))

        if item.name == 'Water':
            item.add_recipe(Recipe(item.name, buildings.get('Water Extractor'), item, 120.0, 1))

        if item.name == 'Crude Oil':
            item.add_recipe(Recipe(item.name, buildings.get('Oil Extractor'), item, 120.0, 1))
            item.add_recipe(Recipe('Poor ' + item.name, buildings.get('Oil Extractor'), item, 60.0, 1))
            item.add_recipe(Recipe('Rich ' + item.name, buildings.get('Oil Extractor'), item, 240.0, 1))

        if item.name == 'Nitrogen Gas':
            item.add_recipe(Recipe(item.name, buildings.get('Resource Well Extractor'), item, 60.0, 1))
            # add poor node
            # add rich node

        items_models[item.name] = item

    return items_models, recipe_models


def load_models(path: str):
    buildings = load_buildings(path)
    items, recipes = load_items(path, buildings)

    return items, recipes, buildings


def find_production_and_demand(depth: int, parent_demands: Dict[str, Demand], preferred_recipes: Dict[str, str]) -> Tuple[Dict[str, ProductionNode], Dict[str, Demand]]:
    sub_demands = {}
    production_nodes = {}

    if ROUND_UP_SCALER_FLAG:
        scaler_calculator = RoundupScalerCalculator
    else:
        scaler_calculator = BasicScalerCalculator

    for demand_name, demand in parent_demands.items():
        if demand.type == DemandType.SINK:
            # TODO: process SINK demands
            # this has to be processed after the full chain of PROD demands is determined
            # this way we can utilize the SINK into the PROD
            continue

        recipe = None
        if demand.item.name in preferred_recipes:
            recipe = RecipeSelector.get_recipe(demand.item.recipes, preferred_recipes.get(demand.item.name))
        if not recipe:
            recipe = RecipeSelector.auto_pick_recipe(demand.item.recipes, demand.item.name)
        if not recipe:
            continue

        # TODO: improve calculation margin by considering production rate of the ingredients and splitter options
        # TODO: add flow rate consideration
        # ## Example:
        # ## need 60/min item1 for prodA and 45/min for prodB, and 15/min prodC - total 120/min
        # ## production output of item1 is 30/min, so to fill demand we need 4 producers
        # ## 2 x producers of item1 can merge for the 60/min feed of prodA
        # ## we need to split one producer to 15/min and feed that to prodC
        # ## and merge the other 15/m to the forth producer, to get 45/m for prodB
        # ## so the output should be something like
        # ## Flow(
        #       sources: {
        #           src1: producer1 @ 20/m,
        #           src2: producer2 @ 20/m,
        #           src3: producer1 @ 20/m,
        #           src4: producer2 @ 20/m,
        #       },
        #       logistics: {
        #           merger1: {
        #               sources: [src1, src2]
        #               outflow: out1
        #           },
        #           splitter1: {
        #               source: src3,
        #               outflows: [tmp1, out3]
        #           },
        #           merger2: {
        #               sources: [src4, tmp1],
        #               outflow: out2
        #           }
        #       },
        #       outflow: {
        #           out1: prodA @ 60/m,
        #           out2: prodB @ 45/m,
        #           out3: prodC @ 15/m,

        production_node_creator = ProductionNodeCreator(demand, recipe, scaler_calculator)
        new_production_node = production_node_creator.generate_production_node(depth, demand.item.name)
        if new_production_node.name in production_nodes:
            production_nodes[new_production_node.name] += new_production_node
        else:
            production_nodes[new_production_node.name] = new_production_node

        accu_prod_node = production_nodes[new_production_node.name]
        # generate sub demands
        demand_creator = DemandCreator(accu_prod_node, accu_prod_node.recipe)
        generated_demands = demand_creator.generate_demands(depth, production_node_creator.scaler)
        new_demands = {gd.name: gd for gd in generated_demands}

        sub_demands = aggregate_models(sub_demands, new_demands)

    return production_nodes, sub_demands


def aggregate_models(models_by_name_1: Dict, models_by_name_2: Dict) -> Dict:
    result_models_by_name = models_by_name_1
    for model2_name, model2 in models_by_name_2.items():
        if result_models_by_name.get(model2_name):
            result_models_by_name[model2_name] += model2
        else:
            result_models_by_name[model2_name] = model2

    return result_models_by_name


def main():

    data = load_models(DATA_PATH)
    items, recipes, buildings = data
    print('Items count:', len(items))
    print('Recipes count:', len(recipes))
    print('Buildings count:', len(buildings))

    # check missing recipes:
    # currently: gathering items (slugs, leaves, etc), ammo (rebars, nobelisk, ammo), waste, specials that can't be crafted (e.g. Superposition Oscillator)
    for item in items.values():
        if not RecipeSelector.auto_pick_recipe(item.recipes, item.name):
            print(item.name, 'has', len(item.recipes), 'recipes; ', len([r for r in item.recipes if r.type == RecipeType.BASIC]), 'BASIC recipes')

    root_demand = {
        'High-Speed Connector': Demand('High-Speed Connector', items['High-Speed Connector'], 3.75, DemandType.PRODUCE, 0),
        'Radio Control Unit': Demand('Radio Control Unit', items['Radio Control Unit'], 5.0, DemandType.PRODUCE, 0),
        'Aluminum Casing': Demand('Aluminum Casing', items['Aluminum Casing'], 80.0, DemandType.PRODUCE, 0),
        'Fuel': Demand('Fuel', items['Fuel'], 60.0, DemandType.PRODUCE, 0),
        'Plastic': Demand('Plastic', items['Plastic'], 15.0, DemandType.PRODUCE, 0),
        'Aluminum Ingot': Demand('Aluminum Ingot', items['Aluminum Ingot'], 30.0, DemandType.SINK, 0),
        'Silica': Demand('Silica', items['Silica'], 100.0, DemandType.SINK, 0),
    }

    preferred_recipes = {
        'Fuel': 'Residual Fuel'
    }

    print('[]'*50)
    new_demand = root_demand
    final_demand = root_demand
    final_production_nodes = {}
    demand_by_depth = {0: root_demand}
    prod_nodes_by_depth = {0: {}}
    for depth in range(1, 10):
        new_nodes, new_demand = find_production_and_demand(depth, new_demand, preferred_recipes)
        # by depth
        demand_by_depth[depth] = new_demand
        prod_nodes_by_depth[depth] = new_nodes
        # # aggregate
        # final_demand = aggregate_models(final_demand, new_demand)
        # final_production_nodes = aggregate_models(final_production_nodes, new_nodes)

    mplfig = plt.figure(figsize=(16.8, 9.6))
    production_graph = nx.DiGraph()

    # reverse aggregate
    for depth in range(10, 0, -1):
        prod_nodes = prod_nodes_by_depth.get(depth)
        if prod_nodes:
            print('-----', final_production_nodes, '|||||||||||', prod_nodes)
            final_production_nodes = aggregate_models(final_production_nodes, prod_nodes)
            print('+++++', final_production_nodes)

    node_labels = {}
    node_positions = {}

    # for depth in range(10):
    #     prod_nodes = prod_nodes_by_depth[depth]
    #     demand_nodes = demand_by_depth[depth]
    #     print('!!!', depth, prod_nodes)
    #     if prod_nodes:
    #         vertical_step = 1 / len(prod_nodes)
    #         for vertical_index, node in enumerate(prod_nodes.values()):
    #             graph_node_name = f'[{depth}] {node.name}'
    #             production_graph.add_node(graph_node_name)
    #             node_labels[graph_node_name] = '{:6.2f}'.format(node.scaled_output) + ' of ' + node.output_item.name
    #             node_positions[graph_node_name] = (1 - depth * 0.1 + random.uniform(-0.05, 0.05), vertical_step * vertical_index)

    vertical_step_by_depth = {d: 1 / (len(nodes)+1) for d, nodes in prod_nodes_by_depth.items()}
    vertical_index_by_depth = {d: vertical_step_by_depth.get(d) for d in prod_nodes_by_depth.keys()}
    for node in final_production_nodes.values():
        graph_node_name = node.name
        production_graph.add_node(graph_node_name)
        node_labels[graph_node_name] = '{:6.2f}'.format(node.building_scale) + 'x' + node.building.name + ' -> {:6.2f}'.format(node.scaled_output) + ' of ' + node.output_item.name
        node_positions[graph_node_name] = (1 - node.depth * 0.1 + random.uniform(-0.03, 0.03), vertical_index_by_depth.get(node.depth))
        vertical_index_by_depth[node.depth] += vertical_step_by_depth.get(node.depth)

    # for depth in range(10):
    #     prod_nodes = prod_nodes_by_depth[depth]
    #     print(']]]', prod_nodes)
    #     if not prod_nodes:
    #         continue
    #
    #     for prod_node in prod_nodes.values():
    #
    #         for ingredient in prod_node.recipe.ingredients:
    #             # supplier = final_production_nodes.get(ingredient.name)
    #             supplier_nodes = prod_nodes_by_depth.get(depth + 1)
    #             if supplier_nodes:
    #                 supplier = supplier_nodes.get(ingredient.name)
    #
    #                 if supplier:
    #                     production_graph.add_edge(f'[{supplier.depth}] {supplier.name}', f'[{depth}] {prod_node.name}')
    #                     print('???????', (f'[{supplier.depth}] {supplier.name}', f'[{depth}] {prod_node.name}'))

    edge_labels = {}
    for node in final_production_nodes.values():
        ingredient_rates_by_ingredient_name = node.recipe.ingredient_rates_by_ingredient_name
        for ingredient in node.recipe.ingredients:
            supplier = final_production_nodes.get(ingredient.name)
            if supplier:
                production_graph.add_edge(supplier.name, node.name)
                edge_labels[(supplier.name, node.name)] = node.building_scale * ingredient_rates_by_ingredient_name.get(ingredient.name)
        #                     print('???????', (f'[{supplier.depth}] {supplier.name}', f'[{depth}] {prod_node.name}'))

    nx.draw(production_graph, pos=node_positions, with_labels=True)
    label_pos = {n: (p[0], p[1] - 0.02) for n, p in node_positions.items()}
    nx.draw_networkx_labels(production_graph, pos=label_pos, labels=node_labels, font_size=6, font_color='r')
    nx.draw_networkx_edge_labels(production_graph, pos=label_pos, edge_labels=edge_labels, font_size=6, font_color='g')

    plt.savefig("depth.png")
    plt.show()


if __name__ == "__main__":
    main()
