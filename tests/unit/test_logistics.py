import pytest
from fastapi.testclient import TestClient

from sftools.api.app import app
from sftools.engine.logistics import (
    BELTS, MERGER, OVERFLOW, SPLITTER, Settings, belts_needed, simulate, validate,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def calculate(client, **plan):
    plan.setdefault("mode", "logistics")
    return client.post("/api/calculate", json=plan).json()


# 5 Steel Beam Constructors (75/min) feeding 30/min to Versatile Framework and 36/min to Encased Beam
BEAMS = {"demands": [{"item": "Versatile Framework", "rate": 5}, {"item": "Encased Industrial Beam", "rate": 12}],
         "merges": {"Encased Industrial Beam__Steel Beam": "Versatile Framework__Steel Beam"}}
STEEL_BEAM = "Versatile Framework__Steel Beam"


def node(body, node_id):
    return next(n for n in body["nodes"] if n["id"] == node_id)


def flows_into(side, target):
    return sum(b["flow"] for b in side["belts"] if b["to"] == target)


def not_fluid(item):
    return False


def test_belts_needed():
    settings = Settings(belt_tier=4)
    assert belts_needed(36, False, settings) == {"kind": "belt", "count": 1, "tier": 1}
    assert belts_needed(600, False, settings) == {"kind": "belt", "count": 2, "tier": 4}  # 2 x 300: more than Mk.3
    assert belts_needed(300, True, Settings(pipe_tier=1)) == {"kind": "pipe", "count": 1, "tier": 1}


def test_simple_mode_has_no_logistics(client):
    body = calculate(client, mode="simple", **BEAMS)
    assert "logistics" not in node(body, STEEL_BEAM)


def test_output_side_groups_buildings_by_destination(client):
    out = node(calculate(client, **BEAMS), STEEL_BEAM)["logistics"]["out"]
    framework, encased = "x|Versatile Framework|Steel Beam", "x|Encased Industrial Beam|Steel Beam"
    assert flows_into(out, framework) == pytest.approx(30)
    assert flows_into(out, encased) == pytest.approx(36)
    # Each exit merges its buildings' belts itself (ticket 036): two mergers, no separate parts
    assert out["complexity"] == 2 and not [n for n in out["nodes"] if n["kind"] in (MERGER, SPLITTER)]
    assert out["backed_up"] == pytest.approx(9)  # 75 made, 66 used: the buildings idle a little
    assert out["warnings"] == [] and not out["edited"]
    # Constructors 3 and 4 straight into the Versatile Framework exit
    assert [b["to"] for b in out["belts"]].count(framework) == 2


def test_input_side_is_a_manifold(client):
    side = node(calculate(client, **BEAMS), STEEL_BEAM)["logistics"]["in"]
    buildings = [n for n in side["nodes"] if n["kind"] == "building"]
    assert len(buildings) == 5 and all(n["delivered"] == pytest.approx(60) for n in buildings)
    assert sum(1 for n in side["nodes"] if n["kind"] == SPLITTER) == 4
    assert sum(1 for n in side["nodes"] if n["kind"] == MERGER) == 1  # the two Steel Ingot entries
    assert side["warnings"] == []


def test_a_belt_tier_too_low_needs_more_belts(client):
    """300 Steel Ingot/min on Mk.1 belts (60): no belt carries more than 60, and the shortfall shows."""
    body = calculate(client, **BEAMS, logistics={"settings": {"belt_tier": 1}})
    side = node(body, STEEL_BEAM)["logistics"]["in"]
    assert all(b["flow"] <= BELTS[0] + 1e-6 for b in side["belts"])
    delivered = sum(n["delivered"] for n in side["nodes"] if n["kind"] == "building")
    assert delivered > 0.9 * 300
    # A merger of two backed-up belts shares 50/50, as in the game: two buildings come up short
    assert len(side["warnings"]) == 2 and all(w.endswith("of 60.00/min") for w in side["warnings"])


def edited(side):
    """The side's layout as the plan stores it."""
    return {"fixed": side["fixed"],
            "nodes": [{"id": n["id"], "kind": n["kind"], "item": n["item"]} for n in side["nodes"]
                      if n["kind"] in (SPLITTER, MERGER, OVERFLOW, "buffer")],
            "belts": [{"from": b["from"], "to": b["to"], "overflow": b.get("overflow", False)} for b in side["belts"]]}


def test_an_edited_layout_is_kept_and_simulated(client):
    out = node(calculate(client, **BEAMS), STEEL_BEAM)["logistics"]["out"]
    layout = edited(out)
    # Send building 5 to a buffer instead: Encased Beam is then short
    layout["nodes"].append({"id": "u1", "kind": "buffer", "item": "Steel Beam"})
    layout["belts"] = [b for b in layout["belts"] if b["from"] != "b5|Steel Beam"] + [{"from": "b5|Steel Beam", "to": "u1"}]
    body = calculate(client, **BEAMS, logistics={"layouts": {f"{STEEL_BEAM}|out": layout}})
    out = node(body, STEEL_BEAM)["logistics"]["out"]
    assert body["logistics_resets"] == [] and out["edited"]
    assert flows_into(out, "x|Encased Industrial Beam|Steel Beam") == pytest.approx(30)
    assert flows_into(out, "u1") == pytest.approx(15)
    assert out["warnings"] == ["Exit to Encased Industrial Beam gets 30.00 of 36.00/min"]


def test_a_layout_that_no_longer_fits_is_reset(client):
    out = node(calculate(client, **BEAMS), STEEL_BEAM)["logistics"]["out"]
    more = {**BEAMS, "demands": [{"item": "Versatile Framework", "rate": 10}, BEAMS["demands"][1]]}
    body = calculate(client, **more, logistics={"layouts": {f"{STEEL_BEAM}|out": edited(out)}})
    assert body["logistics_resets"] == [{"key": f"{STEEL_BEAM}|out", "reason": "the node's buildings or edges changed"}]
    assert not node(body, STEEL_BEAM)["logistics"]["out"]["edited"]


def test_loops_and_ports_are_refused():
    spec = {"side": "out", "items": {"Rotor": {"sources": [("b1", 4.0)], "sinks": [("Motor", 4.0, "Motor")]}}}
    fixed = ["b1|Rotor", "x|Motor|Rotor"]
    loop = {"fixed": fixed, "nodes": [{"id": "s1", "kind": SPLITTER, "item": "Rotor"}, {"id": "m2", "kind": MERGER, "item": "Rotor"}],
            "belts": [{"from": "b1|Rotor", "to": "m2"}, {"from": "m2", "to": "s1"}, {"from": "s1", "to": "m2"},
                      {"from": "s1", "to": "x|Motor|Rotor"}]}
    assert validate(loop, spec, Settings(), not_fluid) == "a loop (only trees for now)"
    two_out = {"fixed": fixed, "nodes": [], "belts": [{"from": "b1|Rotor", "to": "x|Motor|Rotor"}] * 2}
    assert validate(two_out, spec, Settings(), not_fluid) == "too many belts out of b1|Rotor"


def test_overflow_splitter_fills_its_main_output_first():
    spec = {"side": "out", "items": {"Rotor": {"sources": [("b1", 10.0)], "sinks": [("Motor", 6.0, "Motor")]}}}
    fixed = ["b1|Rotor", "x|Motor|Rotor"]
    belts = [{"from": "b1|Rotor", "to": "o1"}, {"from": "o1", "to": "x|Motor|Rotor"}, {"from": "o1", "to": "u2", "overflow": True}]
    parts = [{"id": "o1", "kind": OVERFLOW, "item": "Rotor"}, {"id": "u2", "kind": "buffer", "item": "Rotor"}]
    result = simulate({"fixed": fixed, "nodes": parts, "belts": belts}, spec, Settings(), not_fluid)
    assert flows_into(result, "x|Motor|Rotor") == pytest.approx(6) and flows_into(result, "u2") == pytest.approx(4)

    # A plain splitter shares evenly: the buffer takes half, and the Motor only gets 5
    plain = {"fixed": fixed, "nodes": [{**parts[0], "kind": SPLITTER}, parts[1]], "belts": belts}
    result = simulate(plain, spec, Settings(), not_fluid)
    assert flows_into(result, "x|Motor|Rotor") == pytest.approx(5)
    assert result["warnings"] == ["Exit to Motor gets 5.00 of 6.00/min"]


def test_an_exit_merges_up_to_three_belts_per_line():
    """Ticket 036: an exit has a merger built in, counted with the splitters and mergers."""
    spec = {"side": "out", "items": {"Rotor": {"sources": [(f"b{i}", 4.0) for i in range(1, 5)],
                                               "sinks": [("Motor", 16.0, "Motor")]}}}
    fixed = [f"b{i}|Rotor" for i in range(1, 5)] + ["x|Motor|Rotor"]
    three = {"fixed": fixed, "nodes": [], "belts": [{"from": f"b{i}|Rotor", "to": "x|Motor|Rotor"} for i in range(1, 4)]}
    assert validate(three, spec, Settings(), not_fluid) is None
    assert simulate(three, spec, Settings(), not_fluid)["complexity"] == 1
    four = {**three, "belts": three["belts"] + [{"from": "b4|Rotor", "to": "x|Motor|Rotor"}]}
    assert validate(four, spec, Settings(), not_fluid) == "too many belts into x|Motor|Rotor"
    one = {**three, "belts": three["belts"][:1]}
    assert simulate(one, spec, Settings(), not_fluid)["complexity"] == 0
