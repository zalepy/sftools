"""Heavy Oil Residue left over is burned for power (ticket 055)."""
import pytest
from fastapi.testclient import TestClient

from sftools.api.app import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def calculate(client, **plan):
    plan.setdefault("demands", PLASTIC)
    return client.post("/api/calculate", json=plan).json()


def node(body, node_id):
    return next((n for n in body["nodes"] if n["id"] == node_id), None)


def residue(body, maker):
    return next(b for b in node(body, maker)["byproducts"] if b["item"] == "Heavy Oil Residue")


# 200 Plastic: 10 Refineries making 100 Heavy Oil Residue
PLASTIC = [{"item": "Plastic", "rate": 200}]


def test_residue_left_over_is_burned(client):
    """100 residue: 66.67 Fuel from 2 Refineries, for 4 Generators (3.33 fed) making 833 MW on average."""
    body = calculate(client)
    made = residue(body, "Plastic")
    assert made["burn"] and made["used"] == {"burn": pytest.approx(100)}
    assert node(body, "sink") is None  # nothing for the Sink, which can't take fluids

    burner = node(body, "burn")
    assert burner["burn"] and burner["recipe_name"] == "Residual Fuel"
    assert burner["buildings"] == 2 and burner["ideal_building_scale"] == pytest.approx(5 / 3)
    assert burner["parents"] == ["generators"]
    assert burner["parent_demands"] == {"generators": pytest.approx(200 / 3)}

    generators = node(body, "generators")
    assert generators["buildings"] == 4 and generators["clocks"] == [{"count": 4, "clock": 1.0}]
    assert generators["generators"] == {"fuel": pytest.approx(200 / 3), "fed": pytest.approx(10 / 3),
                                        "power": pytest.approx(2500 / 3), "water": 0.0, "fuels": [
                                            {"item": "Fuel", "rate": pytest.approx(200 / 3),
                                             "fed": pytest.approx(10 / 3), "count": 4}]}
    assert generators["power"] == pytest.approx(2500 / 3)  # generated, so positive
    assert generators["children"] == ["burn"]


def test_the_refinery_takes_clocks_the_generators_follow_the_residue(client):
    """The Refinery is a node like any other; the Generators' count follows the Fuel, at 100%."""
    body = calculate(client, clocks={"burn": [{"clock": 1}, {"count": 1, "clock": 0.6667}]})
    assert node(body, "burn")["clocks"] == [{"count": 1, "clock": 1.0}, {"count": 1, "clock": 0.6667}]
    assert body["ignored"] == []

    more = calculate(client, demands=[{"item": "Plastic", "rate": 300}])  # 150 residue: 100 Fuel
    assert node(more, "generators")["buildings"] == 5
    assert node(more, "generators")["generators"]["fed"] == pytest.approx(5)


def test_residue_used_as_supply_is_not_burned(client):
    """Fuel by Residual Fuel takes the residue first; only the rest is burned."""
    body = calculate(client, demands=[*PLASTIC, {"item": "Fuel", "rate": 40}], recipes={"Fuel": "Residual Fuel"},
                     byproducts_default="use")
    assert residue(body, "Plastic")["used"] == {"Fuel": pytest.approx(60), "burn": pytest.approx(40)}
    assert node(body, "generators")["generators"]["fuel"] == pytest.approx(80 / 3)
    assert node(body, "Fuel")["parent_demands"] == {"External Demand": pytest.approx(40)}  # not the burned Fuel


def test_no_burning_without_residue_left_over(client):
    """All the residue used (up to rounding): no Refinery or Generators shown, as with no residue at all."""
    body = calculate(client, demands=[{"item": "Fuel", "rate": 110}, {"item": "Plastic", "rate": 215},
                                      {"item": "Rubber", "rate": 45}],
                     recipes={"Fuel": "Residual Fuel"}, clocks={"Fuel": [{"clock": 1}, {"count": 1, "clock": 0.83333}]},
                     byproducts_default="use")
    assert node(body, "burn") is None and node(body, "generators") is None
    plain = calculate(client, demands=[{"item": "Smart Plating", "rate": 2}])
    assert node(plain, "burn") is None and node(plain, "generators") is None


def test_burning_has_pipes_and_the_generators_an_input_side(client):
    body = calculate(client, logistics={"settings": {}})
    assert residue(body, "Plastic")["edge_belts"]["burn"]["kind"] == "pipe"
    assert node(body, "burn")["edge_belts"]["generators"]["kind"] == "pipe"
    generators = node(body, "generators")
    assert set(generators["logistics"]) == {"in"}
    buildings = [n for n in generators["logistics"]["in"]["nodes"] if n["kind"] == "building"]
    assert len(buildings) == 4
