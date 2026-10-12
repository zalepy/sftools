import pytest
from fastapi.testclient import TestClient

from sftools.api.app import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def calculate(client, **plan):
    plan.setdefault("demands", [{"item": "Smart Plating", "rate": 2}, {"item": "Modular Frame", "rate": 2}])
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


def test_merges_and_clocks_are_replayed(client):
    nodes = calculate(client).json()["nodes"]
    target, source = sorted(n["id"] for n in nodes_by_item(nodes, "Reinforced Iron Plate"))

    # 5 plates/min merged: one Assembler; at 50% it takes two
    merged = calculate(client, merges={source: target}, clocks={target: [{"clock": 0.5}]}).json()["nodes"]
    rip = nodes_by_item(merged, "Reinforced Iron Plate")
    assert [n["id"] for n in rip] == [target]
    assert rip[0]["constituent_ids"] == [source]
    assert rip[0]["buildings"] == 2
    assert rip[0]["clocks"] == [{"count": 2, "clock": 0.5}]


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
    calculate(client, demands=[{"item": "Rotor", "rate": 4}], clocks={"Rotor": [{"clock": 2.0}]})
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
    assert produced >= needed - 1e-9  # whole buildings: at least what's needed
    assert any(n["id"] == screws_b for n in nodes_by_item(merged, "Screws"))


def test_stale_entries_are_reported_not_rejected(client):
    """tickets/done/009: entries from an older saved plan are skipped and listed, the plan still builds."""
    nodes = calculate(client).json()["nodes"]
    rip = nodes_by_item(nodes, "Reinforced Iron Plate")[0]["id"]
    response = calculate(
        client,
        recipes={"root__Gone": "Iron Plate", rip: "No Such Recipe", nodes[0]["id"]: "Iron Plate"},
        merges={"root__Gone": rip},
        clocks={"root__Gone": [{"clock": 1.5}], rip: [{"clock": 2.0}]},
    )
    assert response.status_code == 200
    body = response.json()
    reported = sorted((e["kind"], e["node_id"], e["reason"]) for e in body["ignored"])
    assert reported == sorted([
        ("recipe", "root__Gone", "node not in plan"),
        ("recipe", rip, "unknown recipe 'No Such Recipe'"),
        ("recipe", nodes[0]["id"], f"'Iron Plate' does not produce {nodes[0]['output_item']}"),
        ("merge", "root__Gone", "node not in plan: root__Gone"),
        ("clock", "root__Gone", "node not in plan"),
    ])
    # The valid clock still applies
    assert next(n for n in body["nodes"] if n["id"] == rip)["clocks"] == [{"count": 1, "clock": 2.0}]


SP_SCREWS = "Smart Plating__Reinforced Iron Plate__Screws"
ROTOR_ROD = "Smart Plating__Rotor__Iron Rod"
ROTOR_SCREWS_ROD = "Smart Plating__Rotor__Screws__Iron Rod"
CAST = {SP_SCREWS: "Alternate: Cast Screws"}


def rods(nodes):
    return {n["id"]: n for n in nodes_by_item(nodes, "Iron Rod")}


def test_switch_drops_a_merged_input_and_keeps_the_rest_of_the_merge(client):
    """Merged Iron Rod, then Screws switched to Cast Screws: only the Screws branch's share goes."""
    demands = [{"item": "Smart Plating", "rate": 2}]
    unmerged = rods(calculate(client, demands=demands).json()["nodes"])
    rotor_rod_alone = unmerged[ROTOR_ROD]["throughput"]

    body = calculate(client, demands=demands, merges={f"{SP_SCREWS}__Iron Rod": ROTOR_ROD}, recipes=CAST).json()
    assert body["ignored"] == [{"kind": "merge", "node_id": f"{SP_SCREWS}__Iron Rod",
                                "reason": "input not used by the current recipe", "dropped": True, "replacement": None}]
    rod = rods(body["nodes"])[ROTOR_ROD]
    assert rod["throughput"] == pytest.approx(rotor_rod_alone)  # the Screws branch's share is gone
    assert rod["constituent_ids"] == []
    assert f"{SP_SCREWS}__Iron Rod" not in rods(body["nodes"])


def test_dropped_merge_target_leaves_the_others_merged(client):
    demands = [{"item": "Smart Plating", "rate": 2}]
    target = f"{SP_SCREWS}__Iron Rod"
    body = calculate(client, demands=demands, recipes=CAST,
                     merges={ROTOR_ROD: target, ROTOR_SCREWS_ROD: target}).json()
    assert sorted((e["node_id"], e["dropped"], e["replacement"]) for e in body["ignored"]) == [
        (ROTOR_ROD, True, None), (ROTOR_SCREWS_ROD, True, ROTOR_ROD)]
    assert rods(body["nodes"])[ROTOR_ROD]["constituent_ids"] == [ROTOR_SCREWS_ROD]


def test_entries_from_older_plans_are_not_marked_dropped(client):
    body = calculate(client, demands=[{"item": "Smart Plating", "rate": 2}],
                     clocks={f"Smart Plating__Reinforced Iron Plate__Alternate: Bolted Iron Plate>Screws": [{"clock": 2}]}).json()
    assert [(e["kind"], e["dropped"]) for e in body["ignored"]] == [("clock", False)]


def test_alternate_recipes_are_marked(client):
    nodes = calculate(client, recipes=CAST).json()["nodes"]
    marked = {n["id"] for n in nodes if n["is_alternate"]}
    assert marked == {SP_SCREWS}


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
    screws = next(n for n in nodes if n["id"] == f"{rip}__Screws")
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
    body = calculate(client, splits={rip: 2}, clocks={f"{rip}~2": [{"clock": 0.5}]}).json()
    assert body["ignored"] == []
    parts = {n["id"]: n for n in nodes_by_item(body["nodes"], "Reinforced Iron Plate") if n["id"].startswith(rip)}
    assert sorted(parts) == [rip, f"{rip}~2"]
    assert parts[f"{rip}~2"]["split"] == {"of": rip, "part": 2, "count": 2}
    assert parts[f"{rip}~2"]["clocks"] == [{"count": 1, "clock": 0.5}]
    assert parts[rip]["clocks"] == [{"count": 1, "clock": 1.0}]
    assert parts[rip]["split"]["part"] == 1


def test_split_with_too_few_parts_is_reported(client):
    rip = "Smart Plating__Reinforced Iron Plate"
    body = calculate(client, splits={rip: 1}).json()
    assert body["ignored"] == [{"kind": "split", "node_id": rip, "reason": "needs at least 2 parts, got 1",
                                "dropped": False, "replacement": None}]


SUPPLIED = "Supplied from outside"


def test_node_supplied_from_outside(client):
    """The node keeps its rate; its inputs, buildings, power and clocks go, quietly."""
    rip = "Smart Plating__Reinforced Iron Plate"
    body = calculate(client, recipes={rip: SUPPLIED}, clocks={rip: [{"clock": 0.5}]}).json()
    nodes = {n["id"]: n for n in body["nodes"]}
    supplied = nodes[rip]
    assert supplied["is_supplied"] and supplied["building"] == "Outside the plan"
    assert supplied["throughput"] == pytest.approx(2.0)  # what Smart Plating needs
    assert supplied["power"] == 0 and supplied["clocks"] == [] and supplied["scaled_inputs"] == []
    assert not any(node_id.startswith(rip + "__") for node_id in nodes)
    assert body["ignored"] == [{"kind": "clock", "node_id": rip, "reason": "supplied from outside: no buildings",
                                "dropped": True, "replacement": None}]
    assert not nodes["Smart Plating"]["is_supplied"]


def test_merge_into_a_supplied_node_is_supplied_too(client):
    nodes = calculate(client).json()["nodes"]
    target, source = sorted(n["id"] for n in nodes_by_item(nodes, "Reinforced Iron Plate"))
    merged = calculate(client, recipes={target: SUPPLIED}, merges={source: target}).json()["nodes"]
    rip = nodes_by_item(merged, "Reinforced Iron Plate")
    assert [n["id"] for n in rip] == [target] and rip[0]["is_supplied"]
    assert rip[0]["throughput"] == pytest.approx(2 + 3)  # 2 for Smart Plating, 3 for Modular Frame
    assert not any(n["id"].startswith(source + "__") for n in merged)  # the absorbed node's inputs go too
