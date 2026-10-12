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


# Leading number only, so units are ignored: "120m3" -> 120, "1,500 MW" -> 1500, "8 m" -> 8
LEADING_NUMBER = re.compile(r'^\s*(-?\d[\d,]*(?:\.\d+)?|-?\.\d+)')


def parse_number(value) -> Optional[float]:
    if value is None or isinstance(value, (int, float)):
        return value
    match = LEADING_NUMBER.match(str(value))
    if not match:
        return None
    return float(match.group(1).replace(',', ''))


def get_int_or_none(data_dict, key) -> Optional[int]:
    number = parse_number(data_dict.get(key))
    return None if number is None else int(number)


def get_float_or_none(data_dict, key) -> Optional[float]:
    return parse_number(data_dict.get(key))


RECIPE_POWER_KEY = re.compile(r'^Power used \((.+)\)$')


def parse_recipe_power(entry: Dict) -> Dict[str, float]:
    """
    Buildings like the Particle Accelerator list power per recipe as a range, e.g.
    'Power used (Diamonds)': '250 - 750'. The game's average draw is the midpoint.
    """
    recipe_power = {}
    for key, value in entry.items():
        match = RECIPE_POWER_KEY.match(key)
        if not match:
            continue
        bounds = [parse_number(part) for part in str(value).split(' - ')]
        bounds = [b for b in bounds if b is not None]
        if bounds:
            recipe_power[match.group(1)] = -sum(bounds) / len(bounds)
    return recipe_power


def load_buildings(path: str) -> Dict[str, Building]:
    with open(os.path.join(path, 'buildings.json'), 'rt', encoding='utf-8') as f:
        buildings_json = json.load(f)

    buildings_by_name = {}

    for entry in buildings_json:
        name = entry.get('name')
        category = NAME_TO_BUILDING_CATEGORY_MAP.get(entry.get('Category'))

        # Negative = consumed, positive = generated
        power = 0
        power_used = parse_number(entry.get('Power used'))
        if power_used is not None:
            power = -int(power_used)
        power_generated = parse_number(entry.get('Power generated'))
        if power_generated is not None:
            power = int(power_generated)

        building = Building(
            name,
            category,
            power,
            get_int_or_none(entry, 'Width'),
            get_int_or_none(entry, 'Length'),
            get_int_or_none(entry, 'Height'),
            get_int_or_none(entry, 'Input'),
            get_int_or_none(entry, 'Output'),
            recipe_power=parse_recipe_power(entry),
        )
        buildings_by_name[name] = building

    return buildings_by_name


def recipe_type_for(recipe_name: str, building_name: str) -> RecipeType:
    if 'Alternate' in recipe_name:
        return RecipeType.ALTERNATE
    if building_name == 'Converter':
        return RecipeType.CONVERSION
    return RecipeType.BASIC


RATE_PRECISION = 0.0051  # the scraped tables round rates to two decimals
ENTRY_PREFIXES = [f'ingredient{i}' for i in range(1, 5)] + ['output1', 'output2']


def cycle_seconds(details: Dict) -> Optional[float]:
    """
    The recipe's cycle time, from its rates and its amounts per cycle (`*_stack`):
    rate = amount * 60 / cycle for every input and output. The scraped rates are rounded to two
    decimals (1.875 shows as 1.88), so this is the simplest cycle time, with the fewest decimals,
    that gives every listed rate back to within that rounding. None if the data doesn't say.
    """
    entries = []
    for prefix in ENTRY_PREFIXES:
        if not details.get(f'{prefix}_name'):
            continue
        rate, amount = get_float_or_none(details, f'{prefix}_rate'), get_float_or_none(details, f'{prefix}_stack')
        if not rate or not amount:
            return None
        entries.append((rate, amount))
    if not entries:
        return None
    rate, amount = max(entries, key=lambda e: e[1])  # the largest amount has the smallest relative rounding error
    estimate = 60 * amount / rate
    for decimals in range(4):
        cycle = round(estimate, decimals)
        if cycle > 0 and all(abs(60 * a / cycle - r) <= RATE_PRECISION for r, a in entries):
            return cycle
    return None


def build_recipe(recipe_name: str, details: Dict, items: Dict[str, Item], buildings: Dict[str, Building]) -> Recipe:
    """
    output1 is the recipe's main product and output2 its by-product, as in the game data.
    Rates are recomputed from the cycle time where possible (see cycle_seconds), so they are exact.
    Ingredients or by-products that refer to unknown items are dropped, and an unknown main product
    is kept as None; tests/unit/test_game_data.py checks there are none.
    """
    cycle = cycle_seconds(details)

    def item_and_rate(prefix):
        rate = get_float_or_none(details, f'{prefix}_rate')
        amount = get_float_or_none(details, f'{prefix}_stack')
        if cycle and amount:
            rate = round(60 * amount / cycle, 9)  # drops float noise such as 25.000000000000004
        return items.get(details.get(f'{prefix}_name')), rate

    def known(prefixes):
        return [(item, rate) for item, rate in map(item_and_rate, prefixes) if item is not None]

    building_name = details.get('building')
    return Recipe(
        name=recipe_name,
        building=buildings.get(building_name),
        product=item_and_rate('output1'),
        byproducts=known(['output2']),
        ingredients=known([f'ingredient{i}' for i in range(1, 5)]),
        type=recipe_type_for(recipe_name, building_name),
    )


def load_items(path: str, buildings: Dict[str, Building]) -> Tuple[Dict[str, Item], Dict[str, Recipe]]:
    with open(os.path.join(path, 'items.json'), 'rt', encoding='utf-8') as f:
        items_json = json.load(f)

    items_by_name: Dict[str, Item] = {}
    for entry in items_json:
        item_name = entry.get('name')
        items_by_name[item_name] = Item(
            item_name,
            NAME_TO_ITEM_CATEGORY_MAP.get(entry.get('Category')),
            get_int_or_none(entry, 'Stack size'),
            get_int_or_none(entry, 'Resource Sink Points'),
            [],
        )

    # Each recipe is listed under every item it outputs; build it once and attach it to each of them.
    recipes_by_name: Dict[str, Recipe] = {}
    for entry in items_json:
        item = items_by_name[entry.get('name')]
        for recipe_name, details in (entry.get('recipes') or {}).items():
            recipe = recipes_by_name.get(recipe_name)
            if recipe is None:
                recipe = build_recipe(recipe_name, details, items_by_name, buildings)
                recipes_by_name[recipe_name] = recipe
            if recipe.output_item is not None and recipe.produces(item.name):
                item.add_recipe(recipe)

    return items_by_name, recipes_by_name


def load_models(path=DATA_DIR) -> Tuple[Dict[str, Item], Dict[str, Recipe], Dict[str, Building]]:
    buildings = load_buildings(path)
    items, recipes = load_items(path, buildings)

    return items, recipes, buildings
