import pytest
from fastapi.testclient import TestClient

from sftools.api.app import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def calculate(client, **plan):
    plan.setdefault("demands", [{"item": "Smart Plating", "rate": 2}, {"item": "Modular Frame", "rate": 2}])
    plan.setdefault("round_up", False)
    return client.post("/api/calculate", json=plan)


def nodes_by_item(nodes, item):
    return [n for n in nodes if n["output_item"] == item]


def test_index_and_health(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    page = client.get("/")
    assert page.status_code == 200
    assert "Smart Plating" in page.text


def test_calculate_is_deterministic(client):
    first = calculate(client).json()["nodes"]
    second = calculate(client).json()["nodes"]
    assert first == second
    assert len(nodes_by_item(first, "Reinforced Iron Plate")) == 2


def test_unknown_item_is_rejected(client):
    response = calculate(client, demands=[{"item": "Unobtainium", "rate": 1}])
    assert response.status_code == 422
    assert "Unobtainium" in response.json()["detail"]


def test_merges_and_overrides_are_replayed(client):
    nodes = calculate(client).json()["nodes"]
    target, source = sorted(n["id"] for n in nodes_by_item(nodes, "Reinforced Iron Plate"))

    merged = calculate(client, merges={source: target}, overrides={target: 3}).json()["nodes"]
    rip = nodes_by_item(merged, "Reinforced Iron Plate")
    assert [n["id"] for n in rip] == [target]
    assert rip[0]["constituent_ids"] == [source]
    assert rip[0]["building_scale"] == 3


def test_merge_of_different_items_is_rejected(client):
    nodes = calculate(client).json()["nodes"]
    rip = nodes_by_item(nodes, "Reinforced Iron Plate")[0]["id"]
    rotor = nodes_by_item(nodes, "Rotor")[0]["id"]
    assert calculate(client, merges={rip: rotor}).status_code == 400


def test_recipe_switch_is_replayed(client):
    demands = [{"item": "Iron Plate", "rate": 20}]
    root = calculate(client, demands=demands).json()["nodes"][0]
    alternates = [
        r["name"] for r in client.get("/api/available_recipes", params={"item_name": "Iron Plate"}).json()
        if r["name"] != root["recipe_name"] and r["output_rate"]
    ]
    assert alternates

    switched = calculate(client, demands=demands, recipes={root["id"]: alternates[0]}).json()["nodes"]
    new_root = next(n for n in switched if n["id"] == root["id"])
    assert new_root["recipe_name"] == alternates[0]


def test_requests_do_not_share_state(client):
    expected = calculate(client).json()["nodes"]
    calculate(client, demands=[{"item": "Rotor", "rate": 4}], overrides={"anything": 9})
    assert calculate(client).json()["nodes"] == expected


def test_merge_into_node_made_dormant_by_recipe_switch(client):
    """tickets/done/008: the merged-in demand must not disappear with the dormant target."""
    nodes = calculate(client).json()["nodes"]
    rip_a, rip_b = sorted(n["id"] for n in nodes_by_item(nodes, "Reinforced Iron Plate"))
    screws_a = next(n["id"] for n in nodes_by_item(nodes, "Screws") if n["parents"] == [rip_a])
    screws_b = next(n["id"] for n in nodes_by_item(nodes, "Screws") if n["parents"] == [rip_b])

    # Merge B's screws into A's, then switch A's plate to a recipe without screws
    merged = calculate(
        client,
        merges={screws_b: screws_a},
        recipes={rip_a: "Alternate: Adhered Iron Plate"},
    ).json()["nodes"]

    produced = sum(n["throughput"] for n in nodes_by_item(merged, "Screws"))
    needed = sum(i["rate"] for n in merged for i in n["scaled_inputs"] if i["item"] == "Screws")
    assert produced == pytest.approx(needed)
    assert any(n["id"] == screws_b for n in nodes_by_item(merged, "Screws"))
