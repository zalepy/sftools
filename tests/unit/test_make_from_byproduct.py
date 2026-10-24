"""Make something from a by-product: a branch sized by what's left of it (ticket 059)."""
import pytest
from fastapi.testclient import TestClient

from sftools.api.app import app

NITRO = {"Rocket Fuel": "Alternate: Nitro Rocket Fuel"}
RESIN = "Rocket Fuel__Fuel|Polymer Resin"  # the Fuel Refineries' resin
BRANCH = "Rocket Fuel__Fuel~Polymer Resin"


def plastic(to="supply"):
    return {RESIN: {"choice": "make", "recipe": "Residual Plastic", "to": to}}


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


def test_resin_left_over_makes_plastic(client):
    """100 Rocket Fuel: 3 Fuel Refineries leave 90 resin, for 1.5 Refineries' worth of Residual Plastic: 30 Plastic."""
    body = calculate(client, [("Rocket Fuel", 100)], recipes=NITRO, byproducts=plastic())
    branch = node(body, BRANCH)
    assert branch["recipe_name"] == "Residual Plastic" and branch["output_item"] == "Plastic"
    assert branch["made_from"] == {"maker": "Rocket Fuel__Fuel", "item": "Polymer Resin", "recipe": "Residual Plastic",
                                   "to": "supply"}
    assert branch["clocks"] == [{"count": 2, "clock": 0.75}]  # all at one clock, taking exactly what's left
    assert branch["throughput"] == pytest.approx(30) and branch["external_demand"] == pytest.approx(30)
    assert byproduct(body, "Rocket Fuel__Fuel", "Polymer Resin")["used"] == {BRANCH: pytest.approx(90)}
    assert byproduct(body, "Rocket Fuel__Fuel", "Polymer Resin")["make"] == {"recipe": "Residual Plastic", "to": "supply"}
    # Its water is mined as usual; its own input of resin, covered by the maker, isn't shown
    assert node(body, BRANCH + "__Water")["parent_demands"] == {BRANCH: pytest.approx(30)}
    assert node(body, BRANCH + "__Polymer Resin") is None
    assert node(body, "sink") is None or all(i["item"] != "Polymer Resin" for i in node(body, "sink")["sink"]["inputs"])
    assert body["made"] == [{"item": "Plastic", "rate": pytest.approx(30), "from": RESIN}]
    assert body["byproducts"][RESIN] == {"choice": "make", "recipe": "Residual Plastic", "to": "supply"}


def test_what_s_made_can_go_to_the_sink(client):
    body = calculate(client, [("Rocket Fuel", 100)], recipes=NITRO, byproducts=plastic("sink"))
    branch = node(body, BRANCH)
    assert branch["external_demand"] == 0 and branch["parent_demands"] == {"sink": pytest.approx(30)}
    assert {"from": BRANCH, "item": "Plastic", "rate": pytest.approx(30), "fluid": False, "waste": False,
            "loop": False, "made": True} in node(body, "sink")["sink"]["inputs"]
    assert body["made"] == []
    assert "x|sink|Plastic" in {n["id"] for n in branch["logistics"]["out"]["nodes"]}


def test_uses_come_first(client):
    """Rubber demanded in the plan (by Residual Rubber: one whole Refinery, 40 resin) takes the resin first."""
    body = calculate(client, [("Rocket Fuel", 100), ("Rubber", 10)], recipes={**NITRO, "Rubber": "Residual Rubber"},
                     byproducts=plastic(), byproducts_default="use")
    assert byproduct(body, "Rocket Fuel__Fuel", "Polymer Resin")["used"] == {
        "Rubber": pytest.approx(40), BRANCH: pytest.approx(50)}
    assert node(body, BRANCH)["throughput"] == pytest.approx(50 / 3)


def test_a_limited_plan_grows_its_branch(client):
    """Rocket Fuel from 300 Crude Oil: 150 resin for 50 Plastic, and the limit holds."""
    body = calculate(client, [("Rocket Fuel", 1)], [("Crude Oil", 300)], recipes=NITRO, supply_limit=True,
                     byproducts=plastic())
    assert body["supply"]["limit"] == "Crude Oil" and body["supply"]["rows"][0]["used"] == pytest.approx(300)
    assert node(body, BRANCH)["throughput"] == pytest.approx(50)
    assert body["made"][0]["rate"] == pytest.approx(50)


def test_choices_per_by_product(client):
    """A per-item choice wins over the node's; a recipe that doesn't take the item is dropped."""
    body = calculate(client, [("Rocket Fuel", 100)], recipes=NITRO,
                     byproducts={"Rocket Fuel": "use", "Rocket Fuel|Compacted Coal": "sink",
                                 RESIN: {"choice": "make", "recipe": "Plastic", "to": "supply"}})
    assert byproduct(body, "Rocket Fuel", "Compacted Coal")["choice"] == "sink"
    assert not byproduct(body, "Rocket Fuel", "Compacted Coal")["burn"]
    assert node(body, BRANCH) is None and RESIN not in body["byproducts"]
    assert body["byproducts"]["Rocket Fuel|Compacted Coal"] == "sink"


def test_recipes_using(client):
    names = [r["name"] for r in client.get("/api/recipes_using", params={"item_name": "Polymer Resin"}).json()]
    assert names == ["Alternate: Polyester Fabric", "Residual Plastic", "Residual Rubber"]
