"""Checks against the real scraped game data (tickets/done/013)."""
import json

import pytest

from sftools.config import DATA_DIR
from sftools.domain.enums.recipe_type import RecipeType
from sftools.engine.calculator import build_plan, default_recipe_for
from sftools.engine.loader import load_models, parse_number

# Gathered or found in the world; everything else must have a recipe (tickets/done/019)
ITEMS_WITHOUT_RECIPES = {
    "Beacon", "Blue Power Slug", "Color Cartridge", "FICSIT Coupon", "Flower Petals", "Hatcher Remains",
    "Hog Remains", "Leaves", "Mycelia", "Purple Power Slug", "Spitter Remains", "Stinger Remains", "Wood",
    "Yellow Power Slug",
}

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
        assert recipe.outputs(), recipe.name
        assert recipe.output_item is not None and recipe.output_rate > 0, recipe.name


def test_rates_are_sane(game):
    _, recipes = game
    for recipe in recipes.values():
        for item, rate in recipe.outputs() + recipe.ingredients:
            assert rate is not None and 0 < rate <= MAX_RATE, (recipe.name, item.name, rate)


def test_rates_are_exact(game):
    """Tickets 025: the scraped tables round to two decimals (1.875 -> 1.88); the loader recomputes from cycle times."""
    _, recipes = game
    turbo_motor = recipes["Turbo Motor"]
    assert turbo_motor.output_rate == 1.875
    supercomputer = recipes["Supercomputer"]
    assert dict((i.name, r) for i, r in supercomputer.ingredients)["High-Speed Connector"] == 5.625
    assert supercomputer.output_rate == 1.875
    electric = recipes["Alternate: Turbo Electric Motor"]  # 64 s cycle: 7 Motors -> 6.5625/min
    assert dict((i.name, r) for i, r in electric.ingredients)["Motor"] == 6.5625
    assert recipes["Alternate: Crystal Computer"].output_rate == pytest.approx(10 / 3)
    assert recipes["Iron Ore (pure) at Miner Mk.3"].output_rate == 480


def test_exact_rates_stay_within_the_scraped_rounding(game, raw_items):
    """Recomputing never moves a rate by more than the two-decimal rounding of the source."""
    _, recipes = game
    scraped = {name: details for entry in raw_items for name, details in (entry.get("recipes") or {}).items()}
    for name, recipe in recipes.items():
        details = scraped[name]

        def listed(prefixes):  # by position: an item can be both input and output (Water in Distilled Silica)
            return [(details[f"{p}_name"], parse_number(details[f"{p}_rate"])) for p in prefixes if details.get(f"{p}_name")]

        for loaded, scraped_entries in ((recipe.ingredients, listed([f"ingredient{i}" for i in range(1, 5)])),
                                        (recipe.outputs(), listed(["output1", "output2"]))):
            assert [item.name for item, _ in loaded] == [item for item, _ in scraped_entries], name
            for (item, rate), (_, listed_rate) in zip(loaded, scraped_entries):
                assert rate == pytest.approx(listed_rate, abs=0.0051), (name, item.name)


def test_fluid_rates_are_not_corrupted(game):
    """'120m3' used to parse as 1203 (tickets/done/003)."""
    _, recipes = game
    alumina = recipes["Alumina Solution"]
    assert [(i.name, r) for i, r in alumina.outputs()] == [("Alumina Solution", 120), ("Silica", 50)]
    assert [(i.name, r) for i, r in alumina.ingredients] == [("Bauxite", 120), ("Water", 180)]
    assert recipes["Unpackage Water"].rate_of("Water") == 120


def test_every_ingredient_is_a_known_item(game, raw_items):
    items, _ = game
    for entry in raw_items:
        for recipe_name, details in (entry.get("recipes") or {}).items():
            for key, name in details.items():
                if key.endswith("_name"):
                    assert name in items, (recipe_name, key, name)


def test_only_world_items_have_no_recipe(game):
    items, _ = game
    assert {i.name for i in items.values() if not i.recipes} == ITEMS_WITHOUT_RECIPES


def test_recipes_from_multi_word_buildings(game):
    """The scraper used to drop every recipe made in e.g. a Particle Accelerator (tickets/done/019)."""
    items, recipes = game
    assert recipes["Diamonds"].building.name == "Particle Accelerator"
    assert [(i.name, r) for i, r in recipes["Diamonds"].ingredients] == [("Coal", 600)]
    assert default_recipe_for(items["Diamonds"]).name == "Diamonds"
    assert recipes["Alien Power Matrix"].building.name == "Quantum Encoder"


def test_converter_recipe_without_ingredients(game):
    _, recipes = game
    epm = recipes["Excited Photonic Matter"]
    assert epm.ingredients == []
    assert epm.rate_of("Excited Photonic Matter") == 200


def test_recipe_power_for_variable_power_buildings(game):
    """Average of the range listed per recipe, e.g. Diamonds '250 - 750' MW."""
    _, recipes = game
    assert recipes["Diamonds"].building.power_for("Diamonds") == -500
    assert recipes["Nuclear Pasta"].building.power_for("Nuclear Pasta") == -1000
    assert recipes["Time Crystal"].building.power_for("Time Crystal") == -250
    assert recipes["Iron Plate"].building.power_for("Iron Plate") == -4


def test_main_product_comes_from_data_not_recipe_name(game):
    """Name guessing failed for recipes like 'Alternate: Bolted Iron Plate' (tickets/done/004)."""
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
    """The first basic recipe used to be picked even when it made something else (tickets/done/005)."""
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
    graph = build_plan(items, recipes, [("Smart Plating", 2)], exact=True)

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
    graph = build_plan(items, recipes, [("Plastic", 20)], exact=True)

    assert node_for(graph, "Plastic").building_scale == pytest.approx(1.0)
    crude = node_for(graph, "Crude Oil")
    assert crude.parent_demands == pytest.approx({node_for(graph, "Plastic").id: 30})
    assert crude.building_scale == pytest.approx(0.5)


def test_node_can_produce_a_byproduct(game):
    """Polymer Resin from the Fuel recipe: 60 Crude Oil -> 40 Fuel + 30 Polymer Resin."""
    items, recipes = game
    root_id = next(iter(build_plan(items, recipes, [("Polymer Resin", 30)]).all_nodes))
    graph = build_plan(items, recipes, [("Polymer Resin", 30)], exact=True, recipes={root_id: "Fuel"})

    root = graph.get_node(root_id)
    assert root.output_item_name == "Polymer Resin"
    assert root.base_output_rate == 30
    assert root.building_scale == pytest.approx(1.0)
    assert node_for(graph, "Crude Oil").parent_demands == pytest.approx({root_id: 60})
