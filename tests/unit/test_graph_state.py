"""Plan replay keeps adjustments and structure (tickets 006, 007, 016, 022)."""
import pytest

from sftools.engine.calculator import build_plan
from sftools.engine.game_data import get_game_data

RIP_SP = "Smart Plating__Reinforced Iron Plate"
RIP_MF = "Modular Frame__Reinforced Iron Plate"
TWO_ROOTS = [("Smart Plating", 2), ("Modular Frame", 2)]


@pytest.fixture(scope="module")
def data():
    return get_game_data()


def scales(graph):
    return {n.id: n.building_scale for n in graph.all_nodes.values() if not n.is_dormant and not n.absorbed_by}


def test_tree_structure_and_ids(data):
    graph = build_plan(data.items, data.recipes, [("Smart Plating", 2)])
    root = graph.get_node("Smart Plating")
    assert sorted(c.output_item_name for c in root.children) == ["Reinforced Iron Plate", "Rotor"]
    assert all(c.id == f"Smart Plating__{c.output_item_name}" for c in root.children)


def test_clocks_survive_merges_and_switches_elsewhere(data):
    """tickets/006: merging or switching recipes used to clear every adjustment in the graph."""
    rotor = "Smart Plating__Rotor"
    graph = build_plan(data.items, data.recipes, TWO_ROOTS, clocks={rotor: [{"clock": 0.5}]},
                       merges={RIP_MF: RIP_SP}, recipes={RIP_SP: "Alternate: Adhered Iron Plate"})
    assert graph.ignored == []
    assert graph.get_node(rotor).building_clocks == [(1, 0.5)]  # 2 Rotors/min: half a building


def test_unmerge_restores_the_plan_exactly(data):
    """tickets/007: unmerging used to lose links added by a recipe switch. Unmerging is replaying without the merge."""
    switched = dict(recipes={RIP_SP: "Alternate: Bolted Iron Plate"})
    before = scales(build_plan(data.items, data.recipes, TWO_ROOTS, exact=True, **switched))
    merged = build_plan(data.items, data.recipes, TWO_ROOTS, exact=True,
                        merges={f"{RIP_MF}__Screws": f"{RIP_SP}__Screws"}, **switched)
    assert merged.get_node(f"{RIP_MF}__Screws").absorbed_by == f"{RIP_SP}__Screws"
    after = scales(build_plan(data.items, data.recipes, TWO_ROOTS, exact=True, **switched))
    assert after == pytest.approx(before)


def test_merged_links_point_to_the_target_in_ui_data(data):
    graph = build_plan(data.items, data.recipes, TWO_ROOTS, merges={RIP_MF: RIP_SP})
    ui = {n["id"]: n for n in graph.get_ui_data()}
    assert RIP_MF not in ui
    assert RIP_SP in ui["Modular Frame"]["children"]
    assert sorted(ui[RIP_SP]["parents"]) == ["Modular Frame", "Smart Plating"]


# --- Node IDs (tickets/done/016) ---



def test_node_ids_are_item_paths(data):
    graph = build_plan(data.items, data.recipes, [("Smart Plating", 2)])
    ids = set(graph.all_nodes)
    assert "Smart Plating" in ids
    assert "Smart Plating__Reinforced Iron Plate__Screws" in ids
    assert max(map(len, ids)) < 120


def test_same_item_demanded_twice_keeps_both(data):
    """Two rows for the same item used to collide on one ID; the 2/min was lost."""
    graph = build_plan(data.items, data.recipes, [("Smart Plating", 2), ("Smart Plating", 3)], exact=True)
    roots = {n.id: n.scaled_output for n in graph.all_nodes.values() if not n.parents}
    assert roots == pytest.approx({"Smart Plating": 2, "Smart Plating#2": 3})


def test_recipe_switch_keeps_shared_inputs_and_drops_the_others(data):
    """Bolted Iron Plate uses Iron Plate and Screws, like the default recipe: both keep their nodes and clocks."""
    rip = "Smart Plating__Reinforced Iron Plate"
    plan = dict(items_map=data.items, recipes_map=data.recipes, demands=[("Smart Plating", 2)])
    slow = [{"clock": 0.25}]

    graph = build_plan(**plan, recipes={rip: "Alternate: Bolted Iron Plate"}, clocks={f"{rip}__Screws": slow})
    assert graph.get_node(f"{rip}__Screws").building_clocks[0][1] == 0.25
    assert graph.ignored == []

    # Cast Screws uses Iron Ingot instead of Iron Rod: the Iron Rod branch and its adjustments go
    screws = f"{rip}__Screws"
    graph = build_plan(**plan, recipes={screws: "Alternate: Cast Screws"},
                       clocks={f"{screws}__Iron Rod": slow, f"{screws}__Iron Rod__Iron Ingot": slow, screws: slow})
    assert graph.get_node(f"{screws}__Iron Rod").is_dormant
    assert not graph.get_node(f"{screws}__Iron Ingot").is_dormant
    assert graph.get_node(screws).building_clocks[0][1] == 0.25
    assert sorted((e["node_id"], e["dropped"]) for e in graph.ignored) == [
        (f"{screws}__Iron Rod", True), (f"{screws}__Iron Rod__Iron Ingot", True)]


def test_inputs_of_a_switched_node_are_rescaled(data):
    """2 Reinforced Iron Plate/min: the Screws node keeps its ID and makes what the running recipe needs."""
    rip = "Smart Plating__Reinforced Iron Plate"
    plan = dict(items_map=data.items, recipes_map=data.recipes, demands=[("Smart Plating", 2)], exact=True)
    for recipe_name in ("Reinforced Iron Plate", "Alternate: Bolted Iron Plate"):
        recipe = data.recipes[recipe_name]
        screws_per_plate = dict((item.name, rate) for item, rate in recipe.ingredients)["Screws"] / recipe.output_rate
        graph = build_plan(**plan, recipes={rip: recipe_name})
        assert graph.get_node(f"{rip}__Screws").scaled_output == pytest.approx(2 * screws_per_plate), recipe_name


def test_old_style_ids_are_reported(data):
    old = "root__Smart Plating__[r]Smart Plating__Reinforced Iron Plate"
    graph = build_plan(data.items, data.recipes, [("Smart Plating", 2)], clocks={old: [{"clock": 2}]},
                       merges={old: "Smart Plating"})
    assert sorted(e["kind"] for e in graph.ignored) == ["clock", "merge"]
