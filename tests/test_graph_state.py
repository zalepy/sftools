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
