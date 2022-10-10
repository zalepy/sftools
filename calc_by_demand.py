import networkx as nx
import matplotlib.pyplot as plt

import json
import os.path
from typing import Optional, Dict, Tuple

from sftools_service.config.default import NAME_TO_BUILDING_CATEGORY_MAP, NAME_TO_ITEM_CATEGORY_MAP
from sftools_service.domain.enums.demand_type import DemandType
from sftools_service.domain.enums.recipe_type import RecipeType
from sftools_service.domain.models.building import Building
from sftools_service.domain.models.demand import Demand
from sftools_service.domain.models.item import Item
from sftools_service.domain.models.production_node import ProductionNode
from sftools_service.domain.models.recipe import Recipe


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

        items_models[item.name] = item

    return items_models, recipe_models


def load_models(path: str):
    buildings = load_buildings(path)
    items, recipes = load_items(path, buildings)

    return items, recipes, buildings


def find_production_and_demand(parent_demands: Dict[str, Demand]) -> Tuple[Dict[str, ProductionNode], Dict[str, Demand]]:
    sub_demands = {}
    production_nodes = {}
    for demand_name, demand in parent_demands.items():
        if demand.type == DemandType.SINK:
            # TODO: process SINK demands
            # this has to be processed after the full chain of PROD demands is determined
            # this way we can utilize the SINK into the PROD
            continue

        # filter alt recipes
        non_alt_recipes = [r for r in demand.item.recipes if r.type == RecipeType.BASIC]
        # pick recipe
        if not non_alt_recipes:
            # print('!!!!!!!!!!!!!!!! Hit leaf recipe for', demand_name)
            continue

        non_alt_recipe = non_alt_recipes[0]
        # print('Demand recipe:', non_alt_recipe.name)

        # determine scale
        # ## round up demands -- this will result in surpluses
        # ## replace with regular division to get float scaler

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

        if ROUND_UP_SCALER_FLAG:
            buildings_needed = demand.rate // non_alt_recipe.output_rate
            if demand.rate % non_alt_recipe.output_rate:
                buildings_needed += 1
        else:
            buildings_needed = demand.rate / non_alt_recipe.output_rate

        scaler = buildings_needed
        # print('Scaler:', scaler, '(', demand.rate, '/', non_alt_recipe.output_rate, ')')

        # generate production set (buildings (type, count), power)
        new_production_node = non_alt_recipe.generate_production_node(scaler)
        if production_nodes.get(non_alt_recipe.name):
            production_nodes[non_alt_recipe.name] += new_production_node
        else:
            production_nodes[non_alt_recipe.name] = new_production_node

        # generate sub demands
        generated_demands = non_alt_recipe.generate_demands(scaler)
        new_demands = {gd.name: gd for gd in generated_demands}

        # for gd in new_demands.values():
        #     print('    >>>', '\n        '.join(str(gd).split('\n')))

        aggregate_models(sub_demands, new_demands)

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

    # root_demand_item = items['Smart Plating']
    # root_demand = {'Smart Plating': Demand('Smart Plating', root_demand_item, 2.0, DemandType.PRODUCE)}
    root_demand = {
        'High-Speed Connector': Demand('High-Speed Connector', items['High-Speed Connector'], 3.75, DemandType.PRODUCE),
        'Radio Control Unit': Demand('Radio Control Unit', items['Radio Control Unit'], 5.0, DemandType.PRODUCE),
        'Aluminum Casing': Demand('Aluminum Casing', items['Aluminum Casing'], 80.0, DemandType.PRODUCE),
        'Fuel': Demand('Fuel', items['Fuel'], 60.0, DemandType.PRODUCE),
        'Plastic': Demand('Plastic', items['Plastic'], 15.0, DemandType.PRODUCE),
        'Aluminum Ingot': Demand('Aluminum Ingot', items['Aluminum Ingot'], 30.0, DemandType.SINK),
        'Silica': Demand('Silica', items['Silica'], 100.0, DemandType.SINK),
    }
    print('[]'*50)
    new_demand = root_demand
    final_demand = root_demand
    final_production_nodes = {}
    for depth in range(10):
        # print('-'*30)
        # print('    >>> depth:', depth)
        new_nodes, new_demand = find_production_and_demand(new_demand)
        # aggregate
        final_demand = aggregate_models(final_demand, new_demand)
        final_production_nodes = aggregate_models(final_production_nodes, new_nodes)

    # print('[]'*10)

    production_graph = nx.DiGraph()
    node_labels = {}
    for node in final_production_nodes.values():
        production_graph.add_node(node.name)
        node_labels[node.name] = '{:6.2f}'.format(node.scaled_output) + ' of ' + node.output_item_name
    leaf_nodes = []
    for production_node in final_production_nodes.values():
        sub_demand = final_demand.get(production_node.name, 0)
        if sub_demand:
            for ingredient_item in sub_demand.item.basic_recipe.ingredients:
                if ingredient_item.name not in final_production_nodes.keys():
                    production_graph.add_node(ingredient_item.name)
    node_pos = nx.planar_layout(production_graph)
    label_pos = {node: (pos[0], pos[1] + 0.05) for node, pos in node_pos.items()}
    for production_node in final_production_nodes.values():
        print('>>> Production Node:', '\n        '.join(str(production_node).split('\n')))
        sub_demand = final_demand.get(production_node.name, 0)
        if sub_demand:
            for ingredient_item in sub_demand.item.basic_recipe.ingredients:
                production_graph.add_edge(ingredient_item.name, production_node.name)
        print('>>> Sub demands:', '\n        '.join(str(sub_demand).split('\n')))
        print('-'*10)

    # nx.draw(production_graph, pos=node_pos, with_labels=True)
    nx.draw_random(production_graph, with_labels=True)
    plt.show()


if __name__ == "__main__":
    main()
