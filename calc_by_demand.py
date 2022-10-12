import random

import networkx as nx
import matplotlib.pyplot as plt

import json
import os.path
from typing import Optional, Dict, Tuple, List

from sftools_service.config.default import NAME_TO_BUILDING_CATEGORY_MAP, NAME_TO_ITEM_CATEGORY_MAP
from sftools_service.domain.basic_scaler_calculator import BasicScalerCalculator
from sftools_service.domain.enums.item_categories import ItemCategory
from sftools_service.domain.enums.recipe_type import RecipeType
from sftools_service.domain.models.building import Building
from sftools_service.domain.models.demand import Demand
from sftools_service.domain.models.ingredient import Ingredient
from sftools_service.domain.models.item import Item
from sftools_service.domain.models.output import Output
from sftools_service.domain.models.product import Product
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
                building_name = recipe_details.get('building')

                ingredient1_name = recipe_details.get('ingredient1_name')
                ingredient1_item = None
                if item_recipe_json_by_name.get(ingredient1_name):
                    ingredient1_item = item_recipe_json_by_name.get(ingredient1_name)[0]
                ingredient1 = None
                if ingredient1_item:
                    ingredient1_rate = get_float_or_none(recipe_details, 'ingredient1_rate', ' /minÂ³')
                    ingredient1_stack = get_int_or_none(recipe_details, 'ingredient1_stack', ' /minÂ³.')
                    ingredient1 = Ingredient(ingredient1_item, ingredient1_rate, ingredient1_stack)

                ingredient2_name = recipe_details.get('ingredient2_name')
                ingredient2_item = None
                if item_recipe_json_by_name.get(ingredient2_name):
                    ingredient2_item = item_recipe_json_by_name.get(ingredient2_name)[0]
                ingredient2 = None
                if ingredient2_item:
                    ingredient2_rate = get_float_or_none(recipe_details, 'ingredient2_rate', ' /minÂ³')
                    ingredient2_stack = get_int_or_none(recipe_details, 'ingredient2_stack', ' /minÂ³.')
                    ingredient2 = Ingredient(ingredient2_item, ingredient2_rate, ingredient2_stack)

                ingredient3_name = recipe_details.get('ingredient3_name')  # "Crystal Oscillator",
                ingredient3_item = None
                if item_recipe_json_by_name.get(ingredient3_name):
                    ingredient3_item = item_recipe_json_by_name.get(ingredient3_name)[0]
                ingredient3 = None
                if ingredient3_item:
                    ingredient3_rate = get_float_or_none(recipe_details, 'ingredient3_rate', ' /minÂ³')
                    ingredient3_stack = get_int_or_none(recipe_details, 'ingredient3_stack', ' /minÂ³.')
                    ingredient3 = Ingredient(ingredient3_item, ingredient3_rate, ingredient3_stack)

                ingredient4_name = recipe_details.get('ingredient4_name')
                ingredient4_item = None
                if item_recipe_json_by_name.get(ingredient4_name):
                    ingredient4_item = item_recipe_json_by_name.get(ingredient4_name)[0]
                ingredient4 = None
                if ingredient4_item:
                    ingredient4_rate = get_float_or_none(recipe_details, 'ingredient4_rate', ' /minÂ³')
                    ingredient4_stack = get_int_or_none(recipe_details, 'ingredient4_stack', ' /minÂ³.')
                    ingredient4 = Ingredient(ingredient4_item, ingredient4_rate, ingredient4_stack)

                output1_name = recipe_details.get('output1_name')
                output1_item = None
                if item_recipe_json_by_name.get(output1_name):
                    output1_item = item_recipe_json_by_name.get(output1_name)[0]
                product1 = None
                if output1_item:
                    output1_rate = get_float_or_none(recipe_details, 'output1_rate', ' /minÂ³')
                    output1_stack = get_int_or_none(recipe_details, 'output1_stack', ' /minÂ³.')
                    product1 = Product(output1_item, output1_rate, output1_stack)

                output2_name = recipe_details.get('output2_name')
                output2_item = None
                if item_recipe_json_by_name.get(output2_name):
                    output2_item = item_recipe_json_by_name.get(output2_name)[0]
                product2 = None
                if output2_item:
                    output2_rate = get_float_or_none(recipe_details, 'output2_rate', ' /minÂ³')
                    output2_stack = get_int_or_none(recipe_details, 'output2_stack', ' /minÂ³.')
                    product2 = Product(output2_item, output2_rate, output2_stack)

                if output1_item:  # when output1_name is only referred inside recipes, and lacks entry in items.json
                    recipe = Recipe(recipe_name, buildings.get(building_name), product1, product2, ingredient1, ingredient2, ingredient3, ingredient4)
                    recipe_models[recipe_name] = recipe
                    item.add_recipe(recipe)

        # hack to add ore mining recipes
        if item.category == ItemCategory.ORES:
            item.add_recipe(Recipe(item.name, buildings.get('Miner Mk.1'), Product(item, 60.0, item.stack_size)))
            item.add_recipe(Recipe('Poor ' + item.name, buildings.get('Miner Mk.1'), Product(item, 30.0, item.stack_size)))
            item.add_recipe(Recipe('Rich ' + item.name, buildings.get('Miner Mk.1'), Product(item, 120.0, item.stack_size)))

        if item.name == 'Water':
            item.add_recipe(Recipe(item.name, buildings.get('Water Extractor'), Product(item, 120.0, 1)))

        if item.name == 'Crude Oil':
            item.add_recipe(Recipe(item.name, buildings.get('Oil Extractor'), Product(item, 120.0, 1)))
            item.add_recipe(Recipe('Poor ' + item.name, buildings.get('Oil Extractor'), Product(item, 60.0, 1)))
            item.add_recipe(Recipe('Rich ' + item.name, buildings.get('Oil Extractor'), Product(item, 240.0, 1)))

        if item.name == 'Nitrogen Gas':
            item.add_recipe(Recipe(item.name, buildings.get('Resource Well Extractor'), Product(item, 60.0, 1)))
            # add poor node
            # add rich node

        items_models[item.name] = item

    return items_models, recipe_models


def load_models(path: str):
    buildings = load_buildings(path)
    items, recipes = load_items(path, buildings)

    return items, recipes, buildings


def find_production_and_demand(depth: int, parent_demands: List[Demand], preferred_recipes: Dict[str, str]) -> Tuple[List[ProductionNode], List[Demand]]:
    sub_demands = []
    production_nodes = []

    if ROUND_UP_SCALER_FLAG:
        scaler_calculator = RoundupScalerCalculator
    else:
        scaler_calculator = BasicScalerCalculator

    for demand in parent_demands:
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
        new_production_node = production_node_creator.generate_production_node(depth, random.uniform(0, 1))
        new_demands = [
            Demand(ingredient.item.name, ingredient.item, ingredient.rate * new_production_node.scaler, depth, new_production_node.name)
            for ingredient in new_production_node.recipe.ingredients]
        new_production_node.inbound_links = [d.uuid for d in new_demands]
        while new_production_node.name in [pn.name for pn in production_nodes]:
            new_production_node.name = new_production_node.name + '*'

        production_nodes.append(new_production_node)
        sub_demands.extend(new_demands)

    return production_nodes, sub_demands


# def aggregate_models(models_by_name_1: Dict, models_by_name_2: Dict) -> Dict:
#     result_models_by_name = models_by_name_1
#     for model2_name, model2 in models_by_name_2.items():
#         if result_models_by_name.get(model2_name):
#             result_models_by_name[model2_name] += model2
#         else:
#             result_models_by_name[model2_name] = model2
#
#     return result_models_by_name


def main():

    data = load_models(DATA_PATH)
    items, recipes, buildings = data
    print('Items count:', len(items))
    print('Recipes count:', len(recipes))
    print('Buildings count:', len(buildings))

    # check missing recipes:
    # currently includes: gathering items (slugs, leaves, etc), ammo (rebars, nobelisk, ammo),
    #                     waste, specials that can't be crafted (e.g. Superposition Oscillator)
    for item in items.values():
        if not RecipeSelector.auto_pick_recipe(item.recipes, item.name):
            print(item.name, 'has', len(item.recipes), 'recipes; ', len([r for r in item.recipes if r.type == RecipeType.BASIC]), 'BASIC recipes')

    root_demand = {
        'High-Speed Connector': Demand('High-Speed Connector', items['High-Speed Connector'], 3.75, 0),
        'Radio Control Unit': Demand('Radio Control Unit', items['Radio Control Unit'], 5.0, 0),
        'Aluminum Casing': Demand('Aluminum Casing', items['Aluminum Casing'], 80.0, 0),
        'Fuel': Demand('Fuel', items['Fuel'], 60.0, 0),
        'Plastic': Demand('Plastic', items['Plastic'], 15.0, 0),
        'Aluminum Ingot': Output('Aluminum Ingot', items['Aluminum Ingot'], 30.0, 10),
        'Silica': Output('Silica', items['Silica'], 100.0, 10),
    }

    preferred_recipes = {
        'Fuel': 'Residual Fuel'
    }

    print('[]'*50)
    # solve demands
    new_demand = root_demand.values()
    all_demand = {rd.uuid: rd for rd in root_demand.values()}
    all_prod_nodes = {}
    prod_nodes_by_depth = {i: [] for i in range(1, 10)}
    for depth in range(1, 10):
        new_nodes, new_demand = find_production_and_demand(depth, new_demand, preferred_recipes)
        for node in new_nodes:
            all_prod_nodes[node.uuid] = node
        prod_nodes_by_depth[depth].extend(new_nodes)
        for demand in new_demand:
            all_demand[demand.uuid] = demand

    # adjust vertical positions of nodes
    for depth in range(1, 10):
        nodes = prod_nodes_by_depth.get(depth)
        if nodes:
            # vertical_step = 1 / (len(nodes) + 1)
            vertical_step = 1 / len(nodes)
            print('>>>> vs', vertical_step, 'ln', len(nodes))
            for i, node in enumerate(nodes):
                node.y_pos = i * vertical_step

    mplfig = plt.figure(figsize=(16.8, 9.6))
    production_graph = nx.DiGraph()
    for node in all_prod_nodes.values():
        node.add_to_nx(production_graph)

    for depth in range(10, 1, -1):
        nodes = prod_nodes_by_depth.get(depth)
        if nodes:
            for node in nodes:
                for node_out_link in node.outbound_links:
                    upstream_nodes = [pn for pn in all_prod_nodes.values() if node_out_link in pn.inbound_links]
                    for upstream_node in upstream_nodes:
                        production_graph.add_edge(node.name, upstream_node.name)

    poses = nx.get_node_attributes(production_graph, 'pos')
    nx.draw(production_graph, pos=poses, with_labels=True)
    label_poses = {n: (p[0], p[1] - 0.01) for n, p in poses.items()}
    nx.draw_networkx_labels(production_graph, pos=label_poses, labels={pn.name: pn.label for pn in all_prod_nodes.values()}, font_size=6, font_color='r')

    plt.savefig("depth.png")
    plt.show()


if __name__ == "__main__":
    main()
