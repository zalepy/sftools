"""
Splitting: a node split into k parts is k nodes, each with an equal share of the demand and its own inputs.
With round_up=False every item must be made exactly as fast as it is consumed.
"""
from collections import defaultdict

import pytest

from sftools.engine.calculator import build_plan
from sftools.engine.game_data import get_game_data

DEMANDS = [("Smart Plating", 2), ("Modular Frame", 2)]
RIP_SP = "Smart Plating__Reinforced Iron Plate"
RIP_MF = "Modular Frame__Reinforced Iron Plate"
BOLTED = "Alternate: Bolted Iron Plate"


@pytest.fixture(scope="module")
def data():
    return get_game_data()


def plan(data, demands=DEMANDS, **kwargs):
    graph = build_plan(data.items, data.recipes, demands, round_up=False, **kwargs)
    assert graph.ignored == []
    return graph


def running(graph):
    return [n for n in graph.all_nodes.values() if not n.is_dormant and not n.absorbed_by]


def assert_balanced(graph):
    made, needed = defaultdict(float), defaultdict(float)
    for node in running(graph):
        made[node.output_item_name] += node.scaled_output
        for inp in node.scaled_inputs:
            needed[inp["item"]] += inp["rate"]
    for node in graph.all_nodes.values():
        if not node.is_dormant and node.external_demand:
            needed[node.output_item_name] += node.external_demand
    for item in made:
        assert made[item] == pytest.approx(needed[item]), item


def total_output(graph, item):
    return sum(n.scaled_output for n in running(graph) if n.output_item_name == item)


def test_split_root_gets_equal_parts_with_their_own_inputs(data):
    graph = plan(data, demands=[("Smart Plating", 2)], splits={"Smart Plating": 2})
    first, second = graph.get_node("Smart Plating"), graph.get_node("Smart Plating~2")
    assert first.external_demand == second.external_demand == 1
    assert first.scaled_output == second.scaled_output == pytest.approx(1)
    assert graph.get_node("Smart Plating~2__Reinforced Iron Plate").parents == {second}
    assert graph.get_node("Smart Plating__Reinforced Iron Plate").parents == {first}
    assert_balanced(graph)


def test_split_inner_node_keeps_the_totals(data):
    unsplit = plan(data)
    graph = plan(data, splits={RIP_SP: 3})
    parts = [graph.get_node(RIP_SP), graph.get_node(f"{RIP_SP}~2"), graph.get_node(f"{RIP_SP}~3")]
    whole = unsplit.get_node(RIP_SP).scaled_output
    assert [p.scaled_output for p in parts] == pytest.approx([whole / 3] * 3)
    assert graph.get_node(f"{RIP_SP}~3__Screws") is not None
    assert_balanced(graph)
    for item in ("Screws", "Iron Plate", "Iron Ore"):
        assert total_output(graph, item) == pytest.approx(total_output(unsplit, item))


def test_parts_round_up_on_their_own(data):
    graph = build_plan(data.items, data.recipes, [("Smart Plating", 2)], round_up=True, splits={"Smart Plating": 2})
    assert graph.get_node("Smart Plating").building_scale == graph.get_node("Smart Plating~2").building_scale == 1


def test_a_part_can_switch_recipe(data):
    graph = plan(data, splits={RIP_SP: 2}, recipes={f"{RIP_SP}~2": BOLTED})
    assert graph.get_node(RIP_SP).recipe.name == "Reinforced Iron Plate"
    assert graph.get_node(f"{RIP_SP}~2").recipe.name == BOLTED
    assert graph.get_node(f"{RIP_SP}~2__{BOLTED}>Screws") is not None
    assert_balanced(graph)


def test_split_below_a_recipe_switch(data):
    switched = f"{RIP_SP}__{BOLTED}>Screws"
    graph = plan(data, recipes={RIP_SP: BOLTED}, splits={switched: 2})
    assert graph.get_node(f"{switched}~2") is not None
    assert_balanced(graph)


def test_part_one_keeps_the_override_and_each_part_has_its_own(data):
    graph = plan(data, splits={RIP_SP: 2}, overrides={RIP_SP: 2, f"{RIP_SP}~2": 0.5})
    assert graph.get_node(RIP_SP).building_scale == 2
    assert graph.get_node(f"{RIP_SP}~2").building_scale == 0.5


def test_merging_the_parts_back(data):
    unsplit = plan(data)
    graph = plan(data, splits={RIP_SP: 2}, merges={f"{RIP_SP}~2": RIP_SP})
    assert graph.get_node(RIP_SP).ideal_building_scale == pytest.approx(unsplit.get_node(RIP_SP).ideal_building_scale)
    assert_balanced(graph)


def test_split_input_of_a_merged_node(data):
    """The parts divide their parent's share of the merged group's need."""
    graph = plan(data, merges={RIP_MF: RIP_SP}, splits={f"{RIP_SP}__Screws": 2})
    assert_balanced(graph)
    sp_parts = [graph.get_node(f"{RIP_SP}__Screws"), graph.get_node(f"{RIP_SP}__Screws~2")]
    mf_screws = graph.get_node(f"{RIP_MF}__Screws")
    # 5 plates/min need 60 Screws/min: 2 plates for Smart Plating, 3 for Modular Frame
    assert [p.scaled_output for p in sp_parts] == pytest.approx([12, 12])
    assert mf_screws.scaled_output == pytest.approx(36)


def test_split_nodes_are_described(data):
    graph = plan(data, splits={RIP_SP: 3})
    assert graph.split_info(RIP_SP) == {"of": RIP_SP, "part": 1, "count": 3}
    assert graph.split_info(f"{RIP_SP}~3") == {"of": RIP_SP, "part": 3, "count": 3}
    assert graph.split_info(RIP_MF) is None
    ui = {n["id"]: n for n in graph.get_ui_data()}
    assert ui[f"{RIP_SP}~2"]["split"] == {"of": RIP_SP, "part": 2, "count": 3}
    assert [step["id"] for step in ui[f"{RIP_SP}~2__Screws"]["derivation"]] == [
        "Smart Plating", f"{RIP_SP}~2", f"{RIP_SP}~2__Screws"]


def test_invalid_and_stale_splits_are_reported(data):
    graph = build_plan(data.items, data.recipes, DEMANDS, round_up=False,
                       splits={RIP_SP: 1, "Smart Plating__Gone": 2})
    assert sorted((e["kind"], e["node_id"]) for e in graph.ignored) == [
        ("split", "Smart Plating__Gone"), ("split", RIP_SP)]
    assert graph.get_node(f"{RIP_SP}~2") is None


def test_split_on_an_inactive_branch_is_kept_silently(data):
    """The split of a Screws node under the default plate recipe applies again when switched back."""
    graph = plan(data, recipes={RIP_SP: BOLTED}, splits={f"{RIP_SP}__Screws": 2})
    assert graph.splits == {f"{RIP_SP}__Screws": 2}


@pytest.mark.parametrize("node_id", [n.id for n in running(build_plan(
    get_game_data().items, get_game_data().recipes, DEMANDS, round_up=False))])
def test_any_split_stays_balanced(data, node_id):
    assert_balanced(plan(data, splits={node_id: 2}))
