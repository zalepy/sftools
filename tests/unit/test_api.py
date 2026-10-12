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


def test_stale_entries_are_reported_not_rejected(client):
    """tickets/done/009: entries from an older saved plan are skipped and listed, the plan still builds."""
    nodes = calculate(client).json()["nodes"]
    rip = nodes_by_item(nodes, "Reinforced Iron Plate")[0]["id"]
    response = calculate(
        client,
        recipes={"root__Gone": "Iron Plate", rip: "No Such Recipe", nodes[0]["id"]: "Iron Plate"},
        merges={"root__Gone": rip},
        overrides={"root__Gone": 3, rip: 2},
    )
    assert response.status_code == 200
    body = response.json()
    reported = sorted((e["kind"], e["node_id"], e["reason"]) for e in body["ignored"])
    assert reported == sorted([
        ("recipe", "root__Gone", "node not in plan"),
        ("recipe", rip, "unknown recipe 'No Such Recipe'"),
        ("recipe", nodes[0]["id"], f"'Iron Plate' does not produce {nodes[0]['output_item']}"),
        ("merge", "root__Gone", "node not in plan: root__Gone"),
        ("override", "root__Gone", "node not in plan"),
    ])
    # The valid override still applies
    assert next(n for n in body["nodes"] if n["id"] == rip)["building_scale"] == 2


def test_entries_on_inactive_branches_are_kept_silently(client):
    """A switch below a recipe that was switched away from must survive, to apply again on switching back."""
    demands = [{"item": "Reinforced Iron Plate", "rate": 5}]
    root = calculate(client, demands=demands).json()["nodes"][0]
    default_screws = next(c for c in root["children"] if "Screws" in c)

    # Under the Bolted recipe: switch its Screws node to Cast Screws
    bolted = calculate(client, demands=demands, recipes={root["id"]: "Alternate: Bolted Iron Plate"}).json()["nodes"]
    bolted_root = next(n for n in bolted if n["id"] == root["id"])
    bolted_screws = next(c for c in bolted_root["children"] if "Screws" in c)
    assert bolted_screws != default_screws

    # Back on the default recipe, the Bolted-branch switch is not stale
    body = calculate(client, demands=demands, recipes={bolted_screws: "Alternate: Cast Screws"}).json()
    assert body["ignored"] == []

    # Under Bolted, a switch for the default branch's (now dormant) Screws node is not stale either
    body = calculate(client, demands=demands, recipes={
        root["id"]: "Alternate: Bolted Iron Plate",
        default_screws: "Alternate: Cast Screws",
        bolted_screws: "Alternate: Cast Screws",
    }).json()
    assert body["ignored"] == []
    assert next(n for n in body["nodes"] if n["id"] == bolted_screws)["recipe_name"] == "Alternate: Cast Screws"


def test_static_assets_are_served(client):
    page = client.get("/").text
    for path in ("/static/app.css", "/static/js/main.js"):
        assert f'{path}?v=' in page
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"
    assert client.get("/static/js/main.js").headers["content-type"].startswith("text/javascript")
    for module in ("api", "state", "graph", "panel"):
        assert client.get(f"/static/js/{module}.js").status_code == 200
    assert 'onclick=' not in page and '<style>' not in page


def test_nodes_carry_their_derivation(client):
    """Each node lists the chain from its demand down to itself, with the recipe each step runs."""
    rip = "Smart Plating__Reinforced Iron Plate"
    nodes = calculate(client, recipes={rip: "Alternate: Bolted Iron Plate"}).json()["nodes"]
    screws = next(n for n in nodes if n["id"] == f"{rip}__Alternate: Bolted Iron Plate>Screws")
    assert [(s["item"], s["recipe"]) for s in screws["derivation"]] == [
        ("Smart Plating", "Smart Plating"),
        ("Reinforced Iron Plate", "Alternate: Bolted Iron Plate"),
        ("Screws", "Screws"),
    ]
    assert screws["derivation"][-1]["id"] == screws["id"]


def test_merged_node_lists_constituent_derivations(client):
    nodes = calculate(client).json()["nodes"]
    target, source = sorted(n["id"] for n in nodes_by_item(nodes, "Reinforced Iron Plate"))
    merged = calculate(client, merges={source: target}).json()["nodes"]
    rip = nodes_by_item(merged, "Reinforced Iron Plate")[0]
    assert [step["item"] for step in rip["constituent_derivations"][0]] == [source.split("__")[0], "Reinforced Iron Plate"]


def test_splits_are_replayed(client):
    rip = "Smart Plating__Reinforced Iron Plate"
    body = calculate(client, splits={rip: 2}, overrides={f"{rip}~2": 0.5}).json()
    assert body["ignored"] == []
    parts = {n["id"]: n for n in nodes_by_item(body["nodes"], "Reinforced Iron Plate") if n["id"].startswith(rip)}
    assert sorted(parts) == [rip, f"{rip}~2"]
    assert parts[f"{rip}~2"]["split"] == {"of": rip, "part": 2, "count": 2}
    assert parts[f"{rip}~2"]["building_scale"] == 0.5
    assert parts[rip]["split"]["part"] == 1


def test_split_with_too_few_parts_is_reported(client):
    rip = "Smart Plating__Reinforced Iron Plate"
    body = calculate(client, splits={rip: 1}).json()
    assert body["ignored"] == [{"kind": "split", "node_id": rip, "reason": "needs at least 2 parts, got 1"}]
