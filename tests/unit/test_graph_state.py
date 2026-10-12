"""In-place FactoryGraph edits: overrides and structure must survive later changes (tickets 006, 007)."""
import pytest

from sftools.domain.enums.demand_type import DemandType
from sftools.domain.models.demand import Demand
from sftools.engine.calculator import calculate_demands, switch_recipe_in_graph
from sftools.engine.game_data import get_game_data


@pytest.fixture(scope="module")
def data():
    return get_game_data()


def build(data, demands):
    return calculate_demands(data.items, [Demand(n, data.items[n], r, DemandType.PRODUCE) for n, r in demands])


def nodes_of(graph, item):
    return sorted(
        (n for n in graph.all_nodes.values() if n.output_item_name == item and not n.is_dormant),
        key=lambda n: n.id,
    )


def active_children(node):
    return sorted(c.output_item_name for c in node.children if not c.is_dormant)


def test_recalculate_without_overrides_keeps_them(data):
    graph = build(data, [("Smart Plating", 2), ("Modular Frame", 2)])
    rotor = nodes_of(graph, "Rotor")[0]
    graph.recalculate({rotor.id: 5}, round_up=True)

    graph.recalculate(round_up=True)
    assert rotor.user_scale == 5

    graph.recalculate({}, round_up=True)
    assert rotor.user_scale is None


def test_merge_and_recipe_switch_keep_overrides(data):
    """tickets/006: both used to clear every user_scale in the graph."""
    graph = build(data, [("Smart Plating", 2), ("Modular Frame", 2)])
    rotor = nodes_of(graph, "Rotor")[0]
    graph.recalculate({rotor.id: 5}, round_up=True)

    source, target = nodes_of(graph, "Reinforced Iron Plate")
    graph.apply_merge(source.id, target.id)
    graph.recalculate(round_up=True)
    assert rotor.user_scale == 5

    switch_recipe_in_graph(graph, target.id, data.recipes["Alternate: Adhered Iron Plate"], data.items)
    assert rotor.user_scale == 5
    assert rotor.building_scale == 5


def test_unmerge_keeps_subtree_from_recipe_switch(data):
    """tickets/007: links added by a recipe switch were lost when the structure was rebuilt."""
    graph = build(data, [("Screws", 40)])
    root = nodes_of(graph, "Screws")[0]
    switch_recipe_in_graph(graph, root.id, data.recipes["Alternate: Cast Screws"], data.items)
    assert active_children(root) == ["Iron Ingot"]

    graph.remove_merge("no-such-merge")  # rebuilds the structure, as any unmerge does
    graph.recalculate(round_up=True)
    assert active_children(root) == ["Iron Ingot"]
    assert nodes_of(graph, "Iron Ingot")[0].building_scale > 0


def test_switch_merge_unmerge_round_trip(data):
    graph = build(data, [("Smart Plating", 2), ("Modular Frame", 2)])
    rip_a, rip_b = nodes_of(graph, "Reinforced Iron Plate")
    switch_recipe_in_graph(graph, rip_a.id, data.recipes["Alternate: Bolted Iron Plate"], data.items)
    graph.recalculate(round_up=False)
    before = {n.id: n.building_scale for n in graph.all_nodes.values() if not n.is_dormant}

    screws_a = next(c for c in rip_a.children if c.output_item_name == "Screws" and not c.is_dormant)
    screws_b = next(c for c in rip_b.children if c.output_item_name == "Screws")
    graph.apply_merge(screws_b.id, screws_a.id)
    graph.recalculate(round_up=False)
    assert screws_b.absorbed_by == screws_a.id

    graph.remove_merge(screws_b.id)
    graph.recalculate(round_up=False)
    after = {n.id: n.building_scale for n in graph.all_nodes.values() if not n.is_dormant}
    assert after == pytest.approx(before)


# --- Node IDs (tickets/done/016) ---

from sftools.engine.calculator import build_plan  # noqa: E402


def test_node_ids_are_item_paths(data):
    graph = build_plan(data.items, data.recipes, [("Smart Plating", 2)])
    ids = set(graph.all_nodes)
    assert "Smart Plating" in ids
    assert "Smart Plating__Reinforced Iron Plate__Screws" in ids
    assert max(map(len, ids)) < 120


def test_same_item_demanded_twice_keeps_both(data):
    """Two rows for the same item used to collide on one ID; the 2/min was lost."""
    graph = build_plan(data.items, data.recipes, [("Smart Plating", 2), ("Smart Plating", 3)], round_up=False)
    roots = {n.id: n.scaled_output for n in graph.all_nodes.values() if not n.parents}
    assert roots == pytest.approx({"Smart Plating": 2, "Smart Plating#2": 3})


def test_recipe_switch_keeps_shared_inputs_and_drops_the_others(data):
    """Bolted Iron Plate uses Iron Plate and Screws, like the default recipe: both keep their nodes and clocks."""
    rip = "Smart Plating__Reinforced Iron Plate"
    plan = dict(items_map=data.items, recipes_map=data.recipes, demands=[("Smart Plating", 2)], round_up=True)
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
    plan = dict(items_map=data.items, recipes_map=data.recipes, demands=[("Smart Plating", 2)], round_up=False)
    for recipe_name in ("Reinforced Iron Plate", "Alternate: Bolted Iron Plate"):
        recipe = data.recipes[recipe_name]
        screws_per_plate = dict((item.name, rate) for item, rate in recipe.ingredients)["Screws"] / recipe.output_rate
        graph = build_plan(**plan, recipes={rip: recipe_name})
        assert graph.get_node(f"{rip}__Screws").scaled_output == pytest.approx(2 * screws_per_plate), recipe_name


def test_old_style_ids_are_reported(data):
    old = "root__Smart Plating__[r]Smart Plating__Reinforced Iron Plate"
    graph = build_plan(data.items, data.recipes, [("Smart Plating", 2)], overrides={old: 3}, merges={old: "Smart Plating"})
    assert sorted(e["kind"] for e in graph.ignored) == ["merge", "override"]
