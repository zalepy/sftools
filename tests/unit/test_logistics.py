import pytest
from fastapi.testclient import TestClient

from sftools.api.app import app
from sftools.engine.logistics import (
    BELTS, MERGER, OVERFLOW, SPLITTER, Settings, belts_for, belts_needed, simulate, validate,
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def calculate(client, **plan):
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


def out_edge(target, rate, item, belts=1):
    """An edge out of node 'p', as side_specs gives it."""
    return (target, rate, target, belts, f"p>{target}|{item}")


def test_belts_needed():
    settings = Settings(belt_tier=4)
    assert belts_needed(36, False, settings) == {"kind": "belt", "count": 1, "tier": 1}
    assert belts_needed(600, False, settings) == {"kind": "belt", "count": 2, "tier": 4}  # 2 x 300: more than Mk.3
    assert belts_needed(300, True, Settings(pipe_tier=1)) == {"kind": "pipe", "count": 1, "tier": 1}


def test_output_side_groups_buildings_by_destination(client):
    out = node(calculate(client, **BEAMS), STEEL_BEAM)["logistics"]["out"]
    framework, encased = "x|Versatile Framework|Steel Beam", "x|Encased Industrial Beam|Steel Beam"
    assert flows_into(out, framework) == pytest.approx(30)
    assert flows_into(out, encased) == pytest.approx(36)
    # Each edge is one belt (ticket 041): the buildings for each merged onto it
    assert out["complexity"] == 2 and sum(1 for n in out["nodes"] if n["kind"] == MERGER) == 2
    assert out["backed_up"] == pytest.approx(9)  # 75 made, 66 used: the buildings idle a little
    assert out["warnings"] == [] and not out["edited"]
    assert [b["to"] for b in out["belts"]].count(framework) == 1


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
    # Each edge comes as 3 belts (ticket 041), each its own entry
    assert sum(1 for n in side["nodes"] if n["kind"] == "entry") == 6
    assert all(b["flow"] <= BELTS[0] + 1e-6 for b in side["belts"])
    delivered = sum(n["delivered"] for n in side["nodes"] if n["kind"] == "building")
    assert delivered >= 0.9 * 300 - 1e-6
    # Belts of 45-55/min merged onto 60/min buildings; a merger of two backed-up belts shares 50/50, as in
    # the game: some buildings come up short
    assert side["warnings"] and all(w.startswith("Building") and w.endswith("of 60.00/min") for w in side["warnings"])


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
    spec = {"side": "out", "items": {"Rotor": {"sources": [("b1", 4.0)], "sinks": [out_edge("Motor", 4.0, "Rotor")]}}}
    fixed = ["b1|Rotor", "x|Motor|Rotor"]
    loop = {"fixed": fixed, "nodes": [{"id": "s1", "kind": SPLITTER, "item": "Rotor"}, {"id": "m2", "kind": MERGER, "item": "Rotor"}],
            "belts": [{"from": "b1|Rotor", "to": "m2"}, {"from": "m2", "to": "s1"}, {"from": "s1", "to": "m2"},
                      {"from": "s1", "to": "x|Motor|Rotor"}]}
    assert validate(loop, spec, Settings(), not_fluid) == "a loop (only trees for now)"
    two_out = {"fixed": fixed, "nodes": [], "belts": [{"from": "b1|Rotor", "to": "x|Motor|Rotor"}] * 2}
    assert validate(two_out, spec, Settings(), not_fluid) == "too many belts out of b1|Rotor"


def test_overflow_splitter_fills_its_main_output_first():
    spec = {"side": "out", "items": {"Rotor": {"sources": [("b1", 10.0)], "sinks": [out_edge("Motor", 6.0, "Rotor")]}}}
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


def test_inputs_that_send_less_than_their_share_leave_the_rest_to_the_others():
    """A merger taking 20 from belts offering 10, 10 and 4: the 4 is all taken, the other two send 8 each."""
    spec = {"side": "out", "items": {"Stator": {"sources": [("b1", 10.0), ("b2", 10.0), ("b3", 4.0)],
                                                "sinks": [out_edge("Motor", 20.0, "Stator")]}}}
    fixed = ["b1|Stator", "b2|Stator", "b3|Stator", "x|Motor|Stator"]
    belts = [{"from": f"b{i}|Stator", "to": "m1"} for i in (1, 2, 3)] + [{"from": "m1", "to": "x|Motor|Stator"}]
    merger = [{"id": "m1", "kind": MERGER, "item": "Stator"}]
    result = simulate({"fixed": fixed, "nodes": merger, "belts": belts}, spec, Settings(), not_fluid)
    assert flows_into(result, "x|Motor|Stator") == pytest.approx(20)
    sent = {n["id"]: n["sent"] for n in result["nodes"] if n["kind"] == "building"}
    assert sent == {"b1|Stator": pytest.approx(8), "b2|Stator": pytest.approx(8), "b3|Stator": pytest.approx(4)}
    assert result["warnings"] == [] and result["backed_up"] == pytest.approx(4)


def test_each_belt_end_takes_one_belt():
    """Ticket 041: an edge of 2 belts has two exits, each taking one belt; they share the edge's rate."""
    spec = {"side": "out", "items": {"Rotor": {"sources": [(f"b{i}", 4.0) for i in range(1, 4)],
                                               "sinks": [out_edge("Motor", 12.0, "Rotor", belts=2)]}}}
    fixed = [f"b{i}|Rotor" for i in range(1, 4)] + ["x|Motor|Rotor", "x|Motor|Rotor|2"]
    layout = {"fixed": fixed, "nodes": [{"id": "m1", "kind": MERGER, "item": "Rotor"}],
              "belts": [{"from": "b1|Rotor", "to": "m1"}, {"from": "b2|Rotor", "to": "m1"},
                        {"from": "m1", "to": "x|Motor|Rotor"}, {"from": "b3|Rotor", "to": "x|Motor|Rotor|2"}]}
    assert validate(layout, spec, Settings(), not_fluid) is None
    result = simulate(layout, spec, Settings(), not_fluid)
    assert flows_into(result, "x|Motor|Rotor") == pytest.approx(8) and flows_into(result, "x|Motor|Rotor|2") == pytest.approx(4)
    assert result["warnings"] == [] and result["complexity"] == 1
    two = {**layout, "belts": layout["belts"][:2] + [{"from": "m1", "to": "x|Motor|Rotor|2"}, {"from": "b3|Rotor", "to": "x|Motor|Rotor|2"}]}
    assert validate(two, spec, Settings(), not_fluid) == "too many belts into x|Motor|Rotor|2"
    # The consumer's side takes 5 on belt 1: the merger backs up, belt 2 can't make up for it
    limited = simulate(layout, spec, Settings(), not_fluid, limits={("p>Motor|Rotor", 1): 5.0})
    assert flows_into(limited, "x|Motor|Rotor") == pytest.approx(5)
    assert limited["warnings"] == ["Exit to Motor gets 9.00 of 12.00/min"]


# Motor 13.5/min on 2 buildings at 100% and one at 70% (10, 10 and 7 Stator/min), from a Stator node
# merged with a demand of 6 (7 Assemblers, 35/min)
MOTORS = {"demands": [{"item": "Motor", "rate": 13.5}, {"item": "Stator", "rate": 6}],
          "merges": {"Stator": "Motor__Stator"}, "clocks": {"Motor": [{"clock": 1}, {"count": 1, "clock": 0.7}]}}
STATOR_TO_MOTOR = "Motor__Stator>Motor|Stator"


def test_an_edge_of_several_belts_follows_the_consumers_buildings(client):
    """Ticket 041: 3 belts to Motor, each feeding one Motor: they carry 10, 10 and 7."""
    body = calculate(client, **MOTORS, logistics={"edges": {STATOR_TO_MOTOR: 3}})
    stator, motor = node(body, "Motor__Stator"), node(body, "Motor")
    assert stator["edge_belts"]["Motor"] == {"kind": "belt", "count": 3, "tier": 1, "needed": 1, "key": STATOR_TO_MOTOR}
    out, into = stator["logistics"]["out"], motor["logistics"]["in"]
    exits = [f"x|Motor|Stator{suffix}" for suffix in ("", "|2", "|3")]
    assert [flows_into(out, e) for e in exits] == [pytest.approx(10), pytest.approx(10), pytest.approx(7)]
    entries = {n["id"]: n["sent"] for n in into["nodes"] if n["kind"] == "entry" and n["item"] == "Stator"}
    assert entries == {"e|Motor__Stator|Stator": pytest.approx(10), "e|Motor__Stator|Stator|2": pytest.approx(10),
                       "e|Motor__Stator|Stator|3": pytest.approx(7)}
    # Each belt straight to its Motor: no splitters or mergers for Stator on the input side
    assert not [n for n in into["nodes"] if n["item"] == "Stator" and n["kind"] in (SPLITTER, MERGER)]
    assert out["warnings"] == [] and into["warnings"] == []

    # One belt (the default): pooled, all 27 still arrive
    body = calculate(client, **MOTORS)
    assert node(body, "Motor__Stator")["edge_belts"]["Motor"]["count"] == 1
    assert flows_into(node(body, "Motor__Stator")["logistics"]["out"], "x|Motor|Stator") == pytest.approx(27)


def test_what_the_consumer_takes_limits_the_producer(client):
    """An input side that takes less on a belt than it's offered: the producer's exit backs up."""
    body = calculate(client, **MOTORS, logistics={"edges": {STATOR_TO_MOTOR: 3}})
    into = node(body, "Motor")["logistics"]["in"]
    # Belt 3 left unconnected on the Motor side: it takes nothing, so its exit gets nothing
    layout = {"fixed": into["fixed"],
              "nodes": [{"id": n["id"], "kind": n["kind"], "item": n["item"]} for n in into["nodes"] if n["kind"] in (SPLITTER, MERGER)],
              "belts": [{"from": b["from"], "to": b["to"], "overflow": b.get("overflow", False)} for b in into["belts"]
                        if not b["from"].startswith("e|Motor__Stator|Stator|3")]}
    body = calculate(client, **MOTORS, logistics={"edges": {STATOR_TO_MOTOR: 3}, "layouts": {"Motor|in": layout}})
    out = node(body, "Motor__Stator")["logistics"]["out"]
    assert flows_into(out, "x|Motor|Stator|3") == pytest.approx(0)
    assert "Exit to Motor gets 20.00 of 27.00/min" in out["warnings"]
    assert "Entry from Motor__Stator (belt 3/3) isn't connected" in node(body, "Motor")["logistics"]["in"]["warnings"]


def test_belts_for_a_chosen_count():
    assert belts_for(27, False, Settings(), 3) == {"kind": "belt", "count": 3, "tier": 1}
    assert belts_for(1500, False, Settings(), 1) == {"kind": "belt", "count": 1, "tier": 6, "over": True}
