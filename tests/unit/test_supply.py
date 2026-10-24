"""Supply-driven power plans: the inbound as the limit, and the generators burning the fuels (ticket 057)."""
import json

import pytest
from fastapi.testclient import TestClient

from sftools.api.app import app
from sftools.config import DATA_DIR
from sftools.domain.models.factory_graph import FactoryGraph
from sftools.domain.models.power import FUELS, GENERATORS, generator_nodes, water_demands


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def calculate(client, demands, inbound, supply_limit=True, **plan):
    body = client.post("/api/calculate", json={"demands": [{"item": i, "rate": r} for i, r in demands],
                                               "inbound": [{"item": i, "rate": r} for i, r in inbound],
                                               "supply_limit": supply_limit, **plan})
    assert body.status_code == 200, body.text
    return body.json()


def node(body, node_id):
    return next((n for n in body["nodes"] if n["id"] == node_id), None)


def row(body, item):
    return next(r for r in body["supply"]["rows"] if r["item"] == item)


def test_burn_rates_follow_the_fuels_energy():
    """The constants against the game data: a generator burns MW × 60 / MJ per minute."""
    raw = {i["name"]: i for i in json.loads((DATA_DIR / "items.json").read_text(encoding="utf-8"))}
    for gen in GENERATORS.values():
        for fuel, rate in gen.fuels.items():
            energy = float(raw[fuel]["Energy"].replace(",", "").removesuffix("MJ"))
            assert rate == pytest.approx(gen.power * 60 / energy), fuel
    assert set(FUELS) == {"Fuel", "Liquid Biofuel", "Turbofuel", "Rocket Fuel", "Ionized Fuel", "Coal",
                          "Compacted Coal", "Petroleum Coke", "Uranium Fuel Rod", "Plutonium Fuel Rod",
                          "Ficsonium Fuel Rod"}


def test_offered_only_for_fuels_with_inbound(client):
    """Without the checkbox, a fuel-only plan with inbound works as before, and says it could use the limit."""
    body = calculate(client, [("Fuel", 100)], [("Crude Oil", 300)], supply_limit=False)
    assert body["supply"] == {"active": False}
    assert node(body, "Fuel")["external_demand"] == pytest.approx(100)
    assert node(body, "generators") is None
    assert calculate(client, [("Fuel", 100), ("Plastic", 10)], [("Crude Oil", 300)])["supply"] is None
    assert calculate(client, [("Fuel", 100)], [])["supply"] is None


def test_crude_oil_feeds_fuel_generators(client):
    """300 Crude Oil: 200 Fuel whatever rate is typed, for 10 Fuel Generators (2,500 MW)."""
    body = calculate(client, [("Fuel", 1)], [("Crude Oil", 300)])
    supply = body["supply"]
    assert supply["active"] and supply["limit"] == "Crude Oil"
    assert supply["demands"] == [{"item": "Fuel", "rate": pytest.approx(200)}]
    assert row(body, "Crude Oil") == {"item": "Crude Oil", "rate": 300, "used": pytest.approx(300), "raw": True,
                                      "limit": True, "unused": False}
    # The raw row sets the limit only: the plan pumps it, no inbound node
    assert node(body, "inbound:Crude Oil") is None
    assert node(body, "Fuel__Crude Oil")["parent_demands"] == {"Fuel": pytest.approx(300)}

    fuel = node(body, "Fuel")
    assert fuel["parents"] == ["generators"] and fuel["parent_demands"] == {"generators": pytest.approx(200)}
    assert fuel["external_demand"] == 0  # no demand circle: the generators burn it
    generators = node(body, "generators")
    assert generators["buildings"] == 10 and generators["power"] == pytest.approx(2500)
    assert generators["children"] == ["Fuel"]
    net = sum(n["power"] for n in body["nodes"])
    assert supply["power"] == {"gross": pytest.approx(2500), "net": pytest.approx(net)}


def test_coal_generators_take_water(client):
    """150 Coal: 10 Coal Generators (750 MW) and their 450 water, from 4 Water Extractors."""
    body = calculate(client, [("Coal", 1)], [("Coal", 150)])
    generators = node(body, "coal-generators")
    assert generators["building"] == "Coal Generator" and generators["buildings"] == 10
    assert generators["generators"]["water"] == pytest.approx(450)
    assert generators["children"] == ["Coal", "Water"]
    water = node(body, "Water")
    assert water["building"] == "Water Extractor" and water["buildings"] == 4
    assert water["parent_demands"] == {"coal-generators": pytest.approx(450)}
    assert body["supply"]["power"]["net"] == pytest.approx(750 - 4 * 20 - 2 * 15)  # Miner Mk.2s: 15 MW each


def test_every_inbound_row_is_a_limit(client):
    """Compacted Coal from 100 Coal and 50 Sulfur: the Sulfur runs out first; Coal shows what's left."""
    body = calculate(client, [("Compacted Coal", 1)], [("Coal", 100), ("Sulfur", 50), ("Iron Ore", 10)])
    assert body["supply"]["limit"] == "Sulfur"
    assert body["supply"]["demands"][0]["rate"] == pytest.approx(50)
    assert row(body, "Coal")["used"] == pytest.approx(50) and not row(body, "Coal")["limit"]
    assert row(body, "Iron Ore")["unused"]  # the plan uses none of it


def test_demand_rates_are_ratios(client):
    """Fuel 2 : Petroleum Coke 1, grown together until the Crude Oil runs out."""
    body = calculate(client, [("Fuel", 2), ("Petroleum Coke", 1)], [("Crude Oil", 600)])
    fuel, coke = (d["rate"] for d in body["supply"]["demands"])
    assert fuel == pytest.approx(2 * coke)
    assert {n["id"] for n in body["nodes"] if n.get("generators")} == {"generators", "coal-generators"}


def test_nothing_used_runs_at_the_typed_rates(client):
    body = calculate(client, [("Fuel", 40)], [("Iron Ore", 100)])
    assert body["supply"]["limit"] is None and row(body, "Iron Ore")["unused"]
    assert node(body, "generators")["generators"]["fuel"] == pytest.approx(40)


def test_other_inbound_rows_stay_inbound(client):
    """Steel Beam for fuel rods is inbound production, as without the limit; nuclear waste can't be sunk."""
    body = calculate(client, [("Uranium Fuel Rod", 1)], [("Uranium", 100), ("Steel Beam", 500)])
    assert body["supply"]["limit"] == "Uranium" and not row(body, "Steel Beam")["raw"]
    assert node(body, "inbound:Steel Beam")["inbound"]["rate"] == 500
    plants = node(body, "nuclear-plants")
    assert plants["generators"]["water"] == pytest.approx(5 * 240)
    assert plants["byproducts"][0]["item"] == "Uranium Waste" and plants["byproducts"][0]["rate"] == pytest.approx(50)
    sink = node(body, "sink")
    assert sink["sink"]["waste"] == ["Uranium Waste"]
    assert {"from": "nuclear-plants", "item": "Uranium Waste", "rate": pytest.approx(50), "fluid": False,
            "waste": True, "loop": False} in sink["sink"]["inputs"]
    assert set(plants["logistics"]) == {"in", "out"}  # waste out to the Sink


def test_the_residue_s_fuel_joins_the_demanded_fuel():
    """One Fuel Generators node: the demanded Fuel and the residue's, counted together as one fuel."""
    graph = FactoryGraph()
    graph.generator_roots = {"Fuel": "generators"}
    fuel = {"id": "Fuel", "output_item": "Fuel", "parents": [], "parent_demands": {"External Demand": 30.0},
            "external_demand": 30.0, "byproducts": []}
    burn = {"id": "burn", "output_item": "Fuel", "parents": ["generators"], "parent_demands": {"generators": 15.0},
            "byproducts": []}
    nodes = generator_nodes(graph, [fuel, burn])
    assert [n["id"] for n in nodes] == ["generators"]
    assert nodes[0]["children"] == ["Fuel", "burn"]
    assert nodes[0]["generators"]["fuels"] == [{"item": "Fuel", "rate": 45.0, "fed": 2.25, "count": 3}]


def test_generators_count_per_fuel_and_cover_byproducts():
    """A generator burns one fuel at a time; a by-product covering the demanded fuel feeds the generators."""
    graph = FactoryGraph()
    graph.generator_roots = {"Turbofuel": "generators", "Fuel": "generators"}
    turbo = {"id": "Turbofuel", "output_item": "Turbofuel", "parents": [], "external_demand": 10.0,
             "parent_demands": {"External Demand": 10.0}, "byproducts": []}
    fuel = {"id": "Fuel", "output_item": "Fuel", "parents": [], "external_demand": 30.0,
            "parent_demands": {"External Demand": 20.0}, "byproducts": []}
    maker = {"id": "maker", "output_item": "X", "parents": [], "parent_demands": {},
             "byproducts": [{"item": "Fuel", "used": {"Fuel": 10.0}}]}
    gen, = generator_nodes(graph, [turbo, fuel, maker])
    assert [(f["item"], f["count"]) for f in gen["generators"]["fuels"]] == [("Turbofuel", 2), ("Fuel", 2)]
    assert gen["buildings"] == 4
    assert maker["byproducts"][0]["used"] == {"generators": 10.0}
    assert fuel["parent_demands"] == {"generators": 20.0}


def test_water_per_kind_of_generator():
    assert water_demands([("Coal", 30), ("Fuel", 20), ("Petroleum Coke", 25), ("Uranium Fuel Rod", 0.4)]) == [
        ("coal-generators", pytest.approx(3 * 45)), ("nuclear-plants", pytest.approx(2 * 240))]
