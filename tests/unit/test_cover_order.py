"""Inbound production and by-products cover a merged node's consumers top down (ticket 062)."""
import pytest
from fastapi.testclient import TestClient

from sftools.api.app import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def nodes(client, **plan):
    body = client.post("/api/calculate", json=plan).json()
    assert body["ignored"] == []
    return {n["id"]: n for n in body["nodes"]}


def test_inbound_covers_a_merged_node_top_down(client):
    """
    Smart Plating 2 and Modular Frame 2, their Reinforced Iron Plate nodes merged (2 + 3 a minute), and 3 inbound:
    Smart Plating, first in the top-down order, gets its 2, Modular Frame the 1 left (not 1.2 and 1.8).
    """
    graph = nodes(client, demands=[{"item": "Smart Plating", "rate": 2}, {"item": "Modular Frame", "rate": 2}],
                  merges={"Smart Plating__Reinforced Iron Plate": "Modular Frame__Reinforced Iron Plate"},
                  inbound=[{"item": "Reinforced Iron Plate", "rate": 3}])
    assert graph["inbound:Reinforced Iron Plate"]["parent_demands"] == {
        "Smart Plating": pytest.approx(2), "Modular Frame": pytest.approx(1)}
    merged = graph["Modular Frame__Reinforced Iron Plate"]
    assert merged["parent_demands"] == {"Modular Frame": pytest.approx(2)}  # what's left to make: 5 - 3, as before


FICSONIUM = "Ficsonium Fuel Rod__Ficsonium"
CRYSTAL = f"{FICSONIUM}__Singularity Cell__Dark Matter Crystal"


def test_a_byproduct_covers_a_merged_node_top_down(client):
    """
    The case that asked for it: 5 Ficsonium Fuel Rods make 100 Dark Matter Residue a minute. Ficsonium needs 200,
    Dark Matter Crystal 150 (one whole building), from one merged residue node: Ficsonium, above, gets all 100.
    """
    graph = nodes(client, demands=[{"item": "Ficsonium Fuel Rod", "rate": 5}],
                  merges={f"{FICSONIUM}__Dark Matter Residue": f"{CRYSTAL}__Dark Matter Residue"},
                  byproducts={"Ficsonium Fuel Rod": "use"})
    residue = next(b for b in graph["Ficsonium Fuel Rod"]["byproducts"] if b["item"] == "Dark Matter Residue")
    assert residue["used"] == {FICSONIUM: pytest.approx(100)}
    merged = graph[f"{CRYSTAL}__Dark Matter Residue"]
    assert merged["parent_demands"] == {FICSONIUM: pytest.approx(100), CRYSTAL: pytest.approx(150)}
    assert merged["ideal_building_scale"] == pytest.approx(2.5)  # 250 left to make, as before
