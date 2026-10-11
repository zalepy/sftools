"""Checks against the real scraped game data (tickets/013)."""
import json

import pytest

from sftools.config import DATA_DIR
from sftools.domain.enums.recipe_type import RecipeType
from sftools.engine.calculator import build_plan, default_recipe_for
from sftools.engine.loader import load_models, parse_number

# Known gaps in the scraped data, tracked in tickets/019.
RECIPES_WITHOUT_OUTPUT = {"Excited Photonic Matter"}
UNKNOWN_INGREDIENTS = {"Hatcher Remains", "Hog Remains", "Spitter Remains", "Stinger Remains"}

MAX_RATE = 1500  # per building per minute; the highest real value is Biomass from Alien Protein


@pytest.fixture(scope="module")
def game():
    items, recipes, buildings = load_models()
    return items, recipes


@pytest.fixture(scope="module")
def raw_items():
    return json.loads((DATA_DIR / "items.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("raw, expected", [
    ("120m3", 120.0),
    ("10m3", 10.0),
    ("22.5", 22.5),
    ("1,500,000MJ", 1500000.0),
    ("250 - 750", 250.0),
    ("8 m", 8.0),
    ("", None),
    (None, None),
    ("n/a", None),
])
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


def test_every_recipe_has_building_and_outputs(game):
    _, recipes = game
    for recipe in recipes.values():
        assert recipe.building is not None, recipe.name
        if recipe.name in RECIPES_WITHOUT_OUTPUT:
            continue
        assert recipe.outputs(), recipe.name
        assert recipe.output_item is not None and recipe.output_rate > 0, recipe.name


def test_rates_are_sane(game):
    _, recipes = game
    for recipe in recipes.values():
        for item, rate in recipe.outputs() + recipe.ingredients():
            assert rate is not None and 0 < rate <= MAX_RATE, (recipe.name, item.name, rate)


def test_fluid_rates_are_not_corrupted(game):
    """'120m3' used to parse as 1203 (tickets/003)."""
    _, recipes = game
    alumina = recipes["Alumina Solution"]
    assert [(i.name, r) for i, r in alumina.outputs()] == [("Alumina Solution", 120), ("Silica", 50)]
    assert [(i.name, r) for i, r in alumina.ingredients()] == [("Bauxite", 120), ("Water", 180)]
    assert recipes["Unpackage Water"].rate_of("Water") == 120


def test_every_ingredient_is_a_known_item(game, raw_items):
    items, _ = game
    for entry in raw_items:
        for recipe_name, details in (entry.get("recipes") or {}).items():
            for key, name in details.items():
                if key.endswith("_name") and name not in UNKNOWN_INGREDIENTS:
                    assert name in items, (recipe_name, key, name)


def test_main_product_comes_from_data_not_recipe_name(game):
    """Name guessing failed for recipes like 'Alternate: Bolted Iron Plate' (tickets/004)."""
    _, recipes = game
    bolted = recipes["Alternate: Bolted Iron Plate"]
    assert bolted.output_item.name == "Reinforced Iron Plate"
    assert bolted.output_rate == 15

    unpackage_oil = recipes["Unpackage Oil"]
    assert unpackage_oil.output_item.name == "Crude Oil"
    assert unpackage_oil.rate_of("Crude Oil") == 60
    assert unpackage_oil.rate_of("Empty Canister") == 60


def test_item_recipes_all_produce_the_item(game):
    items, _ = game
    for item in items.values():
        for recipe in item.recipes:
            assert recipe.produces(item.name), (item.name, recipe.name)


def test_default_recipe_produces_the_item(game):
    """The first basic recipe used to be picked even when it made something else (tickets/005)."""
    items, _ = game
    for item in items.values():
        recipe = default_recipe_for(item)
        if item.recipes:
            assert recipe is not None, item.name
            assert recipe.produces(item.name), (item.name, recipe.name)


@pytest.mark.parametrize("item, expected", [
    ("Silica", "Silica"),
    ("Water", "Water (normal) at Water Extractor"),
    ("Sulfuric Acid", "Sulfuric Acid"),
    ("Crude Oil", "Crude Oil (impure) at Oil Extractor"),
    ("Heavy Oil Residue", "Alternate: Heavy Oil Residue"),
    ("Compacted Coal", "Alternate: Compacted Coal"),
    ("Ficsite Ingot", "Ficsite Ingot (Aluminum)"),
    ("Packaged Fuel", "Packaged Fuel"),
])
def test_default_recipe_choices(game, item, expected):
    items, _ = game
    assert default_recipe_for(items[item]).name == expected


def test_default_recipe_prefers_basic_main_product(game):
    items, _ = game
    for item in items.values():
        recipe = default_recipe_for(item)
        has_basic_main = any(
            r.type == RecipeType.BASIC and r.is_main_product(item.name) and not r.name.startswith("Unpackage")
            for r in item.recipes
        )
        if has_basic_main:
            assert recipe.type == RecipeType.BASIC and recipe.is_main_product(item.name), (item.name, recipe.name)


def test_every_item_plan_builds(game):
    items, recipes = game
    for name, item in items.items():
        if default_recipe_for(item) is None:
            continue
        graph = build_plan(items, recipes, [(name, 10)])
        assert 0 < len(graph.all_nodes) < 500, name


def test_every_recipe_can_be_switched_to(game):
    items, recipes = game
    for name, item in items.items():
        if default_recipe_for(item) is None:
            continue
        root_id = next(iter(build_plan(items, recipes, [(name, 10)]).all_nodes))
        for recipe in item.recipes:
            graph = build_plan(items, recipes, [(name, 10)], recipes={root_id: recipe.name})
            root = graph.get_node(root_id)
            assert root.recipe is recipe, (name, recipe.name)
            assert root.output_item_name == name
            assert root.base_output_rate == recipe.rate_of(name)


def node_for(graph, item):
    nodes = [n for n in graph.all_nodes.values() if n.output_item_name == item and not n.is_dormant]
    assert len(nodes) == 1, (item, [n.id for n in nodes])
    return nodes[0]


def test_golden_smart_plating(game):
    """2/min Smart Plating with exact (unrounded) building counts, from the in-game recipes."""
    items, recipes = game
    graph = build_plan(items, recipes, [("Smart Plating", 2)], round_up=False)

    assert node_for(graph, "Smart Plating").building_scale == pytest.approx(1.0)
    assert node_for(graph, "Reinforced Iron Plate").building_scale == pytest.approx(0.4)
    assert node_for(graph, "Rotor").building_scale == pytest.approx(0.5)

    rip = node_for(graph, "Reinforced Iron Plate")
    rotor = node_for(graph, "Rotor")
    assert {i["item"]: i["rate"] for i in rip.scaled_inputs} == pytest.approx({"Iron Plate": 12, "Screws": 24})
    assert {i["item"]: i["rate"] for i in rotor.scaled_inputs} == pytest.approx({"Iron Rod": 10, "Screws": 50})


def test_golden_fluid_chain(game):
    """20/min Plastic needs 30 m3/min Crude Oil: half an impure Oil Extractor."""
    items, recipes = game
    graph = build_plan(items, recipes, [("Plastic", 20)], round_up=False)

    assert node_for(graph, "Plastic").building_scale == pytest.approx(1.0)
    crude = node_for(graph, "Crude Oil")
    assert crude.parent_demands == pytest.approx({node_for(graph, "Plastic").id: 30})
    assert crude.building_scale == pytest.approx(0.5)


def test_node_can_produce_a_byproduct(game):
    """Polymer Resin from the Fuel recipe: 60 Crude Oil -> 40 Fuel + 30 Polymer Resin."""
    items, recipes = game
    root_id = next(iter(build_plan(items, recipes, [("Polymer Resin", 30)]).all_nodes))
    graph = build_plan(items, recipes, [("Polymer Resin", 30)], round_up=False, recipes={root_id: "Fuel"})

    root = graph.get_node(root_id)
    assert root.output_item_name == "Polymer Resin"
    assert root.base_output_rate == 30
    assert root.building_scale == pytest.approx(1.0)
    assert node_for(graph, "Crude Oil").parent_demands == pytest.approx({root_id: 60})
