"""
Merging: the merged node is shared, each branch keeps its own inputs (tickets/done/020).
With round_up=False every item must be made exactly as fast as it is consumed.
"""
from collections import defaultdict
from itertools import combinations

import pytest

from sftools.engine.calculator import build_plan
from sftools.engine.game_data import get_game_data

DEMANDS = [("Smart Plating", 2), ("Modular Frame", 2)]
RIP_SP = "Smart Plating__Reinforced Iron Plate"
RIP_MF = "Modular Frame__Reinforced Iron Plate"


@pytest.fixture(scope="module")
def data():
    return get_game_data()


def plan(data, demands=DEMANDS, **kwargs):
    graph = build_plan(data.items, data.recipes, demands, round_up=False, **kwargs)
    assert graph.ignored == []
    return graph


def running(graph):
    return [n for n in graph.all_nodes.values() if not n.is_dormant and not n.absorbed_by]


def balance(graph):
    """item -> (made, needed) for every item that has a node."""
    made, needed = defaultdict(float), defaultdict(float)
    for node in running(graph):
        made[node.output_item_name] += node.scaled_output
        for inp in node.scaled_inputs:
            needed[inp["item"]] += inp["rate"]
    for node in graph.all_nodes.values():
        if not node.is_dormant and node.external_demand:
            needed[node.output_item_name] += node.external_demand
    return {item: (made[item], needed[item]) for item in made}


def assert_balanced(graph):
    for item, (made, needed) in balance(graph).items():
        assert made == pytest.approx(needed), item


def test_unmerged_plan_is_balanced(data):
    assert_balanced(plan(data))


def test_merge_same_recipe(data):
    """Used to make 170 Screws/min for 110 needed and 60 Iron Plate for 30."""
    graph = plan(data, merges={RIP_MF: RIP_SP})
    assert_balanced(graph)
    assert balance(graph)["Screws"] == pytest.approx((110, 110))
    assert balance(graph)["Iron Plate"] == pytest.approx((30, 30))


def test_each_branch_keeps_its_inputs_sized_to_its_share(data):
    graph = plan(data, merges={RIP_MF: RIP_SP})
    merged = graph.get_node(RIP_SP)
    assert merged.ideal_building_scale == pytest.approx(0.4 + 0.6)  # 2 + 3 plates/min at 5/min

    # Smart Plating asks 2 of the 5 plates/min, Modular Frame 3
    assert graph.get_node(f"{RIP_SP}__Screws").scaled_output == pytest.approx(60 * 2 / 5)
    assert graph.get_node(f"{RIP_MF}__Screws").scaled_output == pytest.approx(60 * 3 / 5)
    assert graph.get_node(f"{RIP_SP}__Screws").parent_demands == pytest.approx({RIP_SP: 24})


def test_merged_node_running_another_recipe(data):
    """The merged node runs Bolted; the absorbed branch's inputs still supply its share of the same items."""
    graph = plan(data, merges={RIP_MF: RIP_SP}, recipes={RIP_SP: "Alternate: Bolted Iron Plate"})
    assert_balanced(graph)
    bolted_screws = graph.get_node(f"{RIP_SP}__Alternate: Bolted Iron Plate>Screws")
    other_screws = graph.get_node(f"{RIP_MF}__Screws")
    assert other_screws.scaled_output == pytest.approx(1.5 * bolted_screws.scaled_output)  # 3 : 2


def test_absorbed_branch_without_an_input_leaves_it_to_the_others(data):
    """Adhered Iron Plate needs Rubber; only the merged node's own branch has a Rubber node, so it makes all of it."""
    graph = plan(data, merges={RIP_MF: RIP_SP}, recipes={RIP_SP: "Alternate: Adhered Iron Plate"})
    assert_balanced(graph)
    rubber = [n for n in running(graph) if n.output_item_name == "Rubber"]
    assert len(rubber) == 1
    assert graph.get_node(f"{RIP_MF}__Screws").scaled_output == 0  # Adhered uses no Screws


def test_merging_roots_of_the_same_item(data):
    graph = plan(data, demands=[("Rotor", 4), ("Rotor", 6)], merges={"Rotor#2": "Rotor"})
    assert_balanced(graph)
    assert graph.get_node("Rotor").ideal_building_scale == pytest.approx(10 / 4)
    assert graph.get_node("Rotor__Screws").scaled_output == pytest.approx(100 * 4 / 4 * 1)
    assert graph.get_node("Rotor#2__Screws").scaled_output == pytest.approx(100 * 6 / 4)


def test_chained_merges_at_several_levels(data):
    """Merge plates, then the Screws below them, then every remaining same-item pair."""
    graph = plan(data)
    by_item = defaultdict(list)
    for node in running(graph):
        by_item[node.output_item_name].append(node.id)
    merges = {}
    for ids in by_item.values():
        target, *sources = sorted(ids, key=len)
        merges.update({source: target for source in sources})
    assert len(merges) > 5

    merged = plan(data, merges=merges)
    assert_balanced(merged)
    # Totals are the same as without merges
    assert {k: round(v[0], 6) for k, v in balance(merged).items()} == {k: round(v[0], 6) for k, v in balance(graph).items()}


@pytest.mark.parametrize("demands", [
    [("Smart Plating", 2), ("Modular Frame", 2), ("Rotor", 3)],
    [("Motor", 2), ("Rotor", 5)],
    [("Heavy Modular Frame", 1), ("Encased Industrial Beam", 4)],
])
def test_any_pairwise_merge_stays_balanced(data, demands):
    graph = plan(data, demands=demands)
    by_item = defaultdict(list)
    for node in running(graph):
        by_item[node.output_item_name].append(node.id)
    pairs = [pair for ids in by_item.values() for pair in combinations(sorted(ids), 2)][:40]
    assert pairs
    for source, target in pairs:
        assert_balanced(plan(data, demands=demands, merges={source: target}))
