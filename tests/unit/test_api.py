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


def test_preferred_recipes_are_used_for_new_nodes(client):
    """Ticket 043: Screws run Cast Screws everywhere, but a node's own choice still wins."""
    cast = {"Screws": "Alternate: Cast Screws"}
    screws = nodes_by_item(calculate(client, preferred=cast).json()["nodes"], "Screws")
    assert len(screws) == 3 and {n["recipe_name"] for n in screws} == {"Alternate: Cast Screws"}
    # Cast Screws take Iron Ingot: no Iron Rod under them
    assert not [n for n in calculate(client, preferred=cast).json()["nodes"] if n["id"].endswith("__Screws__Iron Rod")]
    first, *others = sorted(n["id"] for n in screws)
    own = nodes_by_item(calculate(client, preferred=cast, recipes={first: "Screws"}).json()["nodes"], "Screws")
    assert {n["id"]: n["recipe_name"] for n in own} == {first: "Screws", **{o: "Alternate: Cast Screws" for o in others}}
    # A recipe switch that brings a new branch: it follows them too
    bolted = calculate(client, demands=[{"item": "Modular Frame", "rate": 2}], preferred=cast,
                       recipes={"Modular Frame": "Alternate: Bolted Frame"}).json()["nodes"]
    assert next(n for n in bolted if n["id"] == "Modular Frame__Screws")["recipe_name"] == "Alternate: Cast Screws"
    # Unknown recipes, and recipes for another item, are left out
    plain = calculate(client, preferred={"Screws": "Iron Rod", "Iron Rod": "Nope"}).json()["nodes"]
    assert {n["recipe_name"] for n in nodes_by_item(plain, "Screws")} == {"Screws"}


def test_recipe_choices(client):
    """The Recipes tab's list: items with more than one recipe, each with its default."""
    choices = {c["item"]: c for c in client.get("/api/recipe_choices").json()}
    screws = choices["Screws"]
    assert screws["default"] == "Screws"
    assert [r["name"] for r in screws["recipes"]] == ["Screws", "Alternate: Cast Screws", "Alternate: Steel Screws"]
    assert all(len(c["recipes"]) > 1 for c in choices.values())
    # Ores too: which node purity and miner the extraction recipes default to
    assert choices["Iron Ore"]["default"] in [r["name"] for r in choices["Iron Ore"]["recipes"]]


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
                     clocks={"Smart Plating__Reinforced Iron Plate__Alternate: Bolted Iron Plate>Screws": [{"clock": 2}]}).json()
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


def test_supplied_from_outside_is_gone(client):
    """Removed with ticket 045: plans that still have it get the node back on its default recipe, with a notice."""
    rip = "Smart Plating__Reinforced Iron Plate"
    body = calculate(client, recipes={rip: "Supplied from outside"}).json()
    nodes = {n["id"]: n for n in body["nodes"]}
    assert nodes[rip]["recipe_name"] == "Reinforced Iron Plate" and not nodes[rip]["is_supplied"]
    assert any(node_id.startswith(rip + "__") for node_id in nodes)
    assert body["ignored"] == [{"kind": "recipe", "node_id": rip, "reason": "unknown recipe 'Supplied from outside'",
                               "dropped": False, "replacement": None}]


def test_inbound_production_covers_demand_top_down(client):
    """3 plates/min inbound: Smart Plating's 2 first (its branch goes), then 1 of Modular Frame's 3."""
    body = calculate(client, inbound=[{"item": "Reinforced Iron Plate", "rate": 3}]).json()
    nodes = {n["id"]: n for n in body["nodes"]}
    assert "Smart Plating__Reinforced Iron Plate" not in nodes
    assert not any(node_id.startswith("Smart Plating__Reinforced Iron Plate__") for node_id in nodes)
    rip_mf = nodes["Modular Frame__Reinforced Iron Plate"]
    assert rip_mf["parent_demands"] == {"Modular Frame": pytest.approx(2.0)}  # 3 needed, 1 inbound

    inbound = nodes["inbound:Reinforced Iron Plate"]
    assert inbound["inbound"] == {"rate": 3.0, "used": pytest.approx(3.0)}
    assert inbound["parent_demands"] == {"Smart Plating": pytest.approx(2.0), "Modular Frame": pytest.approx(1.0)}
    assert inbound["parents"] == ["Modular Frame", "Smart Plating"]
    assert "inbound:Reinforced Iron Plate" in nodes["Smart Plating"]["children"]


def test_inbound_production_beyond_the_demand_is_left_over(client):
    body = calculate(client, inbound=[{"item": "Reinforced Iron Plate", "rate": 4},
                                      {"item": "Reinforced Iron Plate", "rate": 4}]).json()
    rip = nodes_by_item(body["nodes"], "Reinforced Iron Plate")
    assert [n["id"] for n in rip] == ["inbound:Reinforced Iron Plate"]  # nothing left to produce
    assert rip[0]["inbound"] == {"rate": 8.0, "used": pytest.approx(5.0)}


def sink_of(body):
    return next((n for n in body["nodes"] if n["id"] == "sink"), None)


def test_byproducts_go_to_the_sink(client):
    """60 Aluminum Ingot: Alumina Solution makes 100 Silica (sunk) and Aluminum Scrap 120 Water (a fluid)."""
    sink = sink_of(calculate(client, demands=[{"item": "Aluminum Ingot", "rate": 60}]).json())
    assert sorted((i["from"], i["item"], i["rate"], i["fluid"]) for i in sink["sink"]["inputs"]) == [
        ("Aluminum Ingot__Aluminum Scrap", "Water", pytest.approx(120), True),
        ("Aluminum Ingot__Aluminum Scrap__Alumina Solution", "Silica", pytest.approx(100), False),
    ]
    assert sink["sink"]["fluids"] == ["Water"]
    assert sink["buildings"] == 1 and sink["power"] == -30  # one AWESOME Sink for the Silica
    assert sink["throughput"] == pytest.approx(220)


def test_no_sink_without_byproducts(client):
    assert sink_of(calculate(client).json()) is None


def test_sink_follows_the_buildings(client):
    """By-products scale with the maker's buildings and clocks: 2 Refineries at 50% make as much as 1."""
    alumina = "Aluminum Ingot__Aluminum Scrap__Alumina Solution"
    body = calculate(client, demands=[{"item": "Aluminum Ingot", "rate": 60}],
                     clocks={alumina: [{"clock": 0.5}]}).json()
    silica = next(i for i in sink_of(body)["sink"]["inputs"] if i["item"] == "Silica")
    alumina_node = next(n for n in body["nodes"] if n["id"] == alumina)
    assert alumina_node["clocks"] == [{"count": 4, "clock": 0.5}]
    assert silica["rate"] == pytest.approx(100)


ALU = [{"item": "Aluminum Ingot", "rate": 60}]
SCRAP = "Aluminum Ingot__Aluminum Scrap"
ALUMINA = f"{SCRAP}__Alumina Solution"


def byproduct(body, maker, item):
    node = next(n for n in body["nodes"] if n["id"] == maker)
    return next(b for b in node["byproducts"] if b["item"] == item)


def test_byproducts_go_to_the_sink_unless_used(client):
    body = calculate(client, demands=ALU).json()
    assert body["byproducts"] == {}  # the default (Sink) isn't recorded: a later Calculate may still use them
    assert byproduct(body, ALUMINA, "Silica")["used"] == {}


def test_calculate_uses_byproducts_as_supply(client):
    """Aluminum Scrap's 120 Water covers Alumina Solution's; Alumina Solution's 100 Silica covers the 75 needed."""
    body = calculate(client, demands=ALU, byproducts_default="use").json()
    assert body["byproducts"] == {SCRAP: "use", ALUMINA: "use"}
    assert byproduct(body, SCRAP, "Water")["used"] == {ALUMINA: pytest.approx(120)}
    assert byproduct(body, ALUMINA, "Silica")["used"] == {"Aluminum Ingot": pytest.approx(75)}
    ids = {n["id"] for n in body["nodes"]}
    assert "Aluminum Ingot__Silica" not in ids  # nothing left to make
    water = next(n for n in body["nodes"] if n["id"] == f"{ALUMINA}__Water")
    assert water["throughput"] == pytest.approx(240)  # 360 needed, 120 from the by-product
    assert [(i["item"], i["rate"]) for i in sink_of(body)["sink"]["inputs"]] == [("Silica", pytest.approx(25))]


def test_a_choice_in_the_plan_beats_the_default(client):
    body = calculate(client, demands=ALU, byproducts={ALUMINA: "sink"}, byproducts_default="use").json()
    assert body["byproducts"] == {SCRAP: "use", ALUMINA: "sink"}
    assert byproduct(body, ALUMINA, "Silica")["used"] == {}
    assert byproduct(body, SCRAP, "Water")["used"] != {}


def test_byproduct_loop_goes_to_the_sink(client):
    """Water made by the Battery recipe: Aluminum Scrap further down makes Water, which would feed the top node."""
    body = calculate(client, demands=[{"item": "Water", "rate": 10}], recipes={"Water": "Battery"},
                     byproducts_default="use").json()
    scrap = "Water__Aluminum Casing__Aluminum Ingot__Aluminum Scrap"
    water = byproduct(body, scrap, "Water")
    assert water["loop"] and water["used"] == {}
    assert next(i for i in sink_of(body)["sink"]["inputs"] if i["from"] == scrap)["loop"]


BATTERY_WATER = dict(demands=[{"item": "Water", "rate": 100}], recipes={"Water": "Battery"})
LOOP_SCRAP = "Water__Aluminum Casing__Aluminum Ingot__Aluminum Scrap"


def test_solving_a_byproduct_loop(client):
    """100 Water by the Battery recipe: 4 buildings alone; with the loop's Water solved, 3."""
    left_out = calculate(client, **BATTERY_WATER, byproducts={LOOP_SCRAP: "use"}).json()
    assert next(n for n in left_out["nodes"] if n["id"] == "Water")["buildings"] == 4

    body = calculate(client, **BATTERY_WATER, byproducts={LOOP_SCRAP: "solve"}).json()
    assert body["byproducts"] == {LOOP_SCRAP: "solve"}
    water = byproduct(body, LOOP_SCRAP, "Water")
    assert water["loop"] and water["solving"] and water["settled"] and 1 < water["rounds"] <= 100
    assert next(n for n in body["nodes"] if n["id"] == "Water")["buildings"] == 3
    used = sum(water["used"].values())
    assert used == pytest.approx(100 / 3, rel=1e-4)  # the balance on fractional buildings
    assert used <= water["rate"]  # whole buildings make at least that; the rest goes to the Sink


def test_a_loop_that_does_not_settle_is_left_out(client, monkeypatch):
    from sftools.domain.models import factory_graph
    monkeypatch.setattr(factory_graph, "LOOP_ROUNDS", 2)
    body = calculate(client, **BATTERY_WATER, byproducts={LOOP_SCRAP: "solve"}).json()
    water = byproduct(body, LOOP_SCRAP, "Water")
    assert water["solving"] and not water["settled"] and water["used"] == {}
    assert next(n for n in body["nodes"] if n["id"] == "Water")["buildings"] == 4


def test_a_demand_covered_by_inbound_production_stays_shown(client):
    body = calculate(client, demands=[{"item": "Rotor", "rate": 4}], inbound=[{"item": "Rotor", "rate": 10}]).json()
    nodes = {n["id"]: n for n in body["nodes"]}
    assert nodes["Rotor"]["buildings"] == 0
    assert not any(node_id.startswith("Rotor__") for node_id in nodes)  # nothing to make: no inputs
    assert nodes["inbound:Rotor"]["parent_demands"] == {"Rotor": pytest.approx(4)}  # drawn to the demand node


def test_nodes_carry_what_the_user_demands_of_them(client):
    """external_demand: the demand rows of a merge group, also where inbound production covers them."""
    merged = calculate(client, demands=[{"item": "Smart Plating", "rate": 2}, {"item": "Reinforced Iron Plate", "rate": 3}],
                       merges={"Smart Plating__Reinforced Iron Plate": "Reinforced Iron Plate"}).json()["nodes"]
    demanded = {n["id"]: n["external_demand"] for n in merged if n.get("external_demand")}
    assert demanded == {"Smart Plating": pytest.approx(2), "Reinforced Iron Plate": pytest.approx(3)}
    covered = calculate(client, demands=[{"item": "Rotor", "rate": 4}], inbound=[{"item": "Rotor", "rate": 10}]).json()
    assert {n["id"]: n["external_demand"] for n in covered["nodes"] if n.get("external_demand")} == {"Rotor": pytest.approx(4)}


def test_a_rounding_leftover_is_not_sunk(client):
    """Residual Fuel at 2 x 100% + 1 x 83.333% needs 169.9998 of the 170 Heavy Oil Residue its suppliers
    make: the 0.0002 left is rounding (the balance is 83 1/3 %), not a by-product for the Sink."""
    # Plastic (11 Refineries) and Rubber (3) make 110 + 60 Heavy Oil Residue
    body = calculate(client, demands=[{"item": "Fuel", "rate": 110}, {"item": "Plastic", "rate": 215},
                                      {"item": "Rubber", "rate": 45}],
                     recipes={"Fuel": "Residual Fuel"}, clocks={"Fuel": [{"clock": 1}, {"count": 1, "clock": 0.83333}]},
                     byproducts_default="use").json()
    assert not any(i["item"] == "Heavy Oil Residue" for i in (sink_of(body) or {"sink": {"inputs": []}})["sink"]["inputs"])



def test_the_page_and_the_old_logistics_address(client):
    """Logistics is the only mode: the page at /, and the old /logistics address leads there."""
    page = client.get("/")
    assert page.status_code == 200 and 'id="logistics-view"' in page.text and "split-controls" not in page.text
    old = client.get("/logistics", follow_redirects=False)
    assert old.status_code == 301 and old.headers["location"] == "/"
