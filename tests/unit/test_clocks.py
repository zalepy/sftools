"""
Clock speeds per node (ticket 023): the user sets clocks, building counts follow demand and clocks.
Iron Rod: 15/min per Constructor at 100%, 4 MW.
"""
import pytest

from sftools.domain.models.production_node import CLOCK_POWER_EXPONENT
from sftools.engine.calculator import build_plan, parse_clock_groups
from sftools.engine.game_data import get_game_data

ROD = [("Iron Rod", 144)]


@pytest.fixture(scope="module")
def data():
    return get_game_data()


def rod(data, clocks=None, demands=ROD, **kwargs):
    graph = build_plan(data.items, data.recipes, demands, round_up=True, clocks=clocks, **kwargs)
    assert graph.ignored == []
    return graph.get_node("Iron Rod"), graph


def all_at(clock, last=None):
    return [{"clock": clock}] + ([{"count": 1, "clock": last}] if last is not None else [])


def test_default_is_whole_buildings_at_100(data):
    node, _ = rod(data)
    assert node.buildings == 10  # 9.6 rounded up
    assert node.building_clocks == [(10, 1.0)]
    assert node.scaled_output == 150


def test_a_faster_last_building_saves_one(data):
    node, _ = rod(data, {"Iron Rod": all_at(1.0, last=2.0)})
    assert node.buildings == 9
    assert node.building_clocks == [(8, 1.0), (1, 2.0)]
    assert node.scaled_output == 150


def test_the_last_building_is_never_tuned_automatically(data):
    """10 x 100% makes 150 for 144: the surplus stays, as set."""
    node, _ = rod(data, {"Iron Rod": all_at(1.0, last=1.0)})
    assert node.scaled_output == 150
    assert node.ideal_building_scale == pytest.approx(9.6)


def test_slower_clock_needs_more_buildings(data):
    node, _ = rod(data, {"Iron Rod": all_at(0.5)})
    assert node.building_clocks == [(20, 0.5)]  # 144 / 7.5 = 19.2
    assert node.scaled_output == 150


def test_inputs_follow_what_the_buildings_use(data):
    _, graph = rod(data, {"Iron Rod": all_at(1.0, last=2.0)})
    assert graph.get_node("Iron Rod__Iron Ingot").ideal_building_scale * 30 == pytest.approx(150)


def test_buildings_follow_demand(data):
    clocks = {"Iron Rod": all_at(1.0, last=2.0)}
    assert rod(data, clocks, demands=[("Iron Rod", 160)])[0].building_clocks == [(9, 1.0), (1, 2.0)]
    # A small demand: the last building alone covers it
    assert rod(data, clocks, demands=[("Iron Rod", 10)])[0].building_clocks == [(1, 2.0)]


def test_power_and_shards(data):
    node, _ = rod(data, {"Iron Rod": all_at(1.0, last=2.0)})
    assert node.scaled_power == pytest.approx(-4 * (8 + 2.0 ** CLOCK_POWER_EXPONENT))
    assert node.power_shards == 2
    assert rod(data, {"Iron Rod": all_at(2.5)})[0].power_shards == 4 * 3  # 144 / 37.5 -> 4 buildings
    assert rod(data, {"Iron Rod": all_at(1.5)})[0].power_shards == 7  # 144 / 22.5 -> 7 buildings
    assert rod(data, {"Iron Rod": all_at(0.8)})[0].power_shards == 0


def test_merged_node_uses_the_targets_clocks(data):
    rip_sp, rip_mf = "Smart Plating__Reinforced Iron Plate", "Modular Frame__Reinforced Iron Plate"
    graph = build_plan(data.items, data.recipes, [("Smart Plating", 2), ("Modular Frame", 2)], round_up=True,
                       merges={rip_mf: rip_sp}, clocks={rip_sp: all_at(0.5), rip_mf: all_at(2.5)})
    assert graph.get_node(rip_sp).building_clocks == [(2, 0.5)]  # 5 plates/min at 2.5 per building
    assert graph.get_node(rip_mf).building_scale == 0


def test_exact_mode_ignores_clocks(data):
    graph = build_plan(data.items, data.recipes, ROD, round_up=False, clocks={"Iron Rod": all_at(0.5)})
    assert graph.get_node("Iron Rod").building_scale == pytest.approx(9.6)


@pytest.mark.parametrize("groups, reason", [
    ([], "expected a list of clock groups"),
    ([{"clock": 1.0}, {"clock": 0.5}], "exactly one group must have no count"),
    ([{"count": 1, "clock": 1.0}], "exactly one group must have no count"),
    ([{"clock": 1.0}, {"count": 0, "clock": 0.5}], "a group's count must be a whole number of at least 1"),
    ([{"clock": 3.0}], "clock 300% is outside 1%-250%"),
    ([{"count": 1}], "each group needs a clock"),
])
def test_invalid_clocks_are_reported(data, groups, reason):
    with pytest.raises(ValueError, match=reason):
        parse_clock_groups(groups)
    graph = build_plan(data.items, data.recipes, ROD, round_up=True, clocks={"Iron Rod": groups})
    assert graph.ignored == [{"kind": "clock", "node_id": "Iron Rod", "reason": reason}]


def test_saved_overrides_are_reported_once(data):
    graph = build_plan(data.items, data.recipes, ROD, round_up=True, overrides={"Iron Rod": 3})
    assert [(e["kind"], e.get("dropped", False)) for e in graph.ignored] == [("override", False)]
    assert graph.get_node("Iron Rod").buildings == 10
