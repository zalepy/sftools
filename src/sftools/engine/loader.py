import json
import os.path
import re
from typing import Dict, Optional, Tuple

from sftools.config import DATA_DIR
from sftools.domain.enums.recipe_type import RecipeType
from sftools.domain.models.building import Building
from sftools.domain.models.item import Item
from sftools.domain.models.recipe import Recipe
from sftools.engine.category_maps import NAME_TO_BUILDING_CATEGORY_MAP, NAME_TO_ITEM_CATEGORY_MAP


def get_int_or_none(data_dict, key, strippings=None) -> Optional[int]:
    value_as_str = data_dict.get(key)
    if not value_as_str:
        return None
    try:
        # Remove anything that isn't a digit, minus, or comma/period
        cleaned = re.sub(r'[^-0-9]', '', value_as_str)
        if not cleaned: return None
        return int(cleaned)
    except (ValueError, AttributeError) as ex:
        print('failed converting', key, ': >' + value_as_str + '< to int')
        return None


def get_float_or_none(data_dict, key, strippings=None) -> Optional[float]:
    value_as_str = data_dict.get(key)
    if not value_as_str:
        return None
    try:
        # Keep digits, minus, and one decimal point
        cleaned = re.sub(r'[^-0-9.]', '', value_as_str.replace(',', ''))
        if not cleaned: return None
        return float(cleaned)
    except (ValueError, AttributeError) as ex:
        print('failed converting', key, ': >' + value_as_str + '< to float')
        return None


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


def load_models(path=DATA_DIR):
    buildings = load_buildings(path)
    items, recipes = load_items(path, buildings)

    return items, recipes, buildings
