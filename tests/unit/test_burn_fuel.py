"""Fuel by-products left over are burned in their generators (ticket 058)."""
import pytest
from fastapi.testclient import TestClient

from sftools.api.app import app

NITRO = {"Rocket Fuel": "Alternate: Nitro Rocket Fuel"}  # Fuel, Nitrogen, Sulfur, Coal -> Rocket Fuel + Compacted Coal


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def calculate(client, demands, inbound=(), **plan):
    body = client.post("/api/calculate", json={"demands": [{"item": i, "rate": r} for i, r in demands],
                                               "inbound": [{"item": i, "rate": r} for i, r in inbound], **plan})
    assert body.status_code == 200, body.text
    return body.json()


def node(body, node_id):
    return next((n for n in body["nodes"] if n["id"] == node_id), None)


def byproduct(body, maker, item):
    return next(b for b in node(body, maker)["byproducts"] if b["item"] == item)


def test_a_solid_fuel_left_over_feeds_coal_generators(client):
    """100 Rocket Fuel by Nitro: 25 Compacted Coal left over, for 4 Coal Generators and their water."""
    body = calculate(client, [("Rocket Fuel", 100)], recipes=NITRO)
    coal = byproduct(body, "Rocket Fuel", "Compacted Coal")
    assert coal["burn"] and coal["fuel"] and coal["burned"] == pytest.approx(25)
    assert coal["used"] == {"coal-generators": pytest.approx(25)}
    generators = node(body, "coal-generators")
    assert generators["generators"]["fuels"] == [{"item": "Compacted Coal", "rate": pytest.approx(25),
                                                  "fed": pytest.approx(3.5), "count": 4}]
    assert generators["children"] == ["Rocket Fuel", "Water"]
    assert node(body, "Water")["parent_demands"] == {"coal-generators": pytest.approx(3.5 * 45)}
    assert node(body, "Water")["external_demand"] == 0  # the generators' water, not a demand target
    assert all(i["item"] != "Compacted Coal" for i in node(body, "sink")["sink"]["inputs"])
    assert body["supply"] is None  # not a plan of fuels only: burning applies to every plan
    # The maker's output side has an exit to the generators, whose input side takes it
    assert "x|coal-generators|Compacted Coal" in {n["id"] for n in node(body, "Rocket Fuel")["logistics"]["out"]["nodes"]}


def test_uses_come_first(client):
    """Compacted Coal demanded elsewhere takes the by-product first; only the rest is burned."""
    body = calculate(client, [("Rocket Fuel", 100), ("Compacted Coal", 10)], recipes=NITRO, byproducts_default="use")
    coal = byproduct(body, "Rocket Fuel", "Compacted Coal")
    assert coal["used"] == {"Compacted Coal": pytest.approx(10), "coal-generators": pytest.approx(15)}


def test_the_sink_chosen_keeps_a_solid_fuel_for_the_sink(client):
    """Only a Sink the plan records: the default for nodes not listed is the Sink, and that burns."""
    sunk = calculate(client, [("Rocket Fuel", 100)], recipes=NITRO, byproducts={"Rocket Fuel": "sink"})
    coal = byproduct(sunk, "Rocket Fuel", "Compacted Coal")
    assert not coal["burn"] and coal["used"] == {}
    assert node(sunk, "coal-generators") is None and node(sunk, "Water") is None
    assert {"from": "Rocket Fuel", "item": "Compacted Coal", "rate": pytest.approx(25), "fluid": False,
            "waste": False, "loop": False} in node(sunk, "sink")["sink"]["inputs"]

    burned = calculate(client, [("Rocket Fuel", 100)], recipes=NITRO, byproducts={"Rocket Fuel": "burn"})
    assert byproduct(burned, "Rocket Fuel", "Compacted Coal")["burned"] == pytest.approx(25)
    assert burned["byproducts"]["Rocket Fuel"] == "burn"  # kept in the plan


def test_a_fluid_fuel_is_always_burned(client):
    """Polymer Resin made by the Fuel recipe has Fuel as its by-product: it can't be sunk, Sink chosen or not."""
    body = calculate(client, [("Fabric", 30)], recipes={"Fabric": "Alternate: Polyester Fabric",
                                                        "Fabric__Polymer Resin": "Fuel"},
                     byproducts={"Fabric__Polymer Resin": "sink"})
    fuel = byproduct(body, "Fabric__Polymer Resin", "Fuel")
    assert fuel["burn"] and fuel["burned"] == pytest.approx(40)
    assert node(body, "generators")["generators"]["fuels"][0]["item"] == "Fuel"
    assert node(body, "sink") is None


def test_a_limited_plan_burns_them_too(client):
    """Rocket Fuel from 300 Crude Oil: 50 Compacted Coal for 7 Coal Generators, in the summary's power."""
    body = calculate(client, [("Rocket Fuel", 1)], [("Crude Oil", 300)], recipes=NITRO, supply_limit=True)
    assert node(body, "coal-generators")["buildings"] == 7
    assert body["supply"]["power"]["gross"] == pytest.approx(300 / (25 / 6) * 250 + 7 * 75)


def test_a_demanded_fuel_covered_by_byproducts_is_not_shown(client):
    """The workaround from before: a Compacted Coal row the by-product covers entirely isn't shown at 0/min."""
    body = calculate(client, [("Rocket Fuel", 6), ("Compacted Coal", 1)], [("Crude Oil", 300)], recipes=NITRO,
                     supply_limit=True, byproducts_default="use")
    assert node(body, "Compacted Coal") is None
    assert byproduct(body, "Rocket Fuel", "Compacted Coal")["used"] == {"coal-generators": pytest.approx(50)}
    assert node(body, "coal-generators")["generators"]["fuels"][0]["rate"] == pytest.approx(50)
