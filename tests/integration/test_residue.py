"""Browser tests of burning Heavy Oil Residue for power (ticket 055; see conftest.py). The sizing is unit-tested in tests/unit/test_residue.py."""
import json

SAVED = "JSON.parse(localStorage.getItem('sf_logistics_state'))"
PLASTIC = {"items": ["Plastic"], "rates": [200], "clocks": {}, "merges": {}, "recipes": {}}
EDGES = r"(globalThis.end = n => n.id().replace(/\|(in|out)$/, ''), document.getElementById('cy')._cyreg.cy.edges())"


def label(node_id):
    return f"document.getElementById('cy')._cyreg.cy.getElementById({json.dumps(node_id)}).data('label')"


def edge(source, target):
    return f"{EDGES}.filter(e => end(e.source()) === {json.dumps(source)} && end(e.target()) === {json.dumps(target)})"


def text(element_id):
    return f"document.getElementById({json.dumps(element_id)}).textContent"


def test_residue_is_burned_by_a_refinery_and_generators(page):
    page.open(page.base_url, PLASTIC)
    assert "sink" not in page.node_ids()
    assert page.js(label("generators")) == "Power\n833.33 MW\n(4× Fuel Generator, 3.33 fed)"
    assert page.js(label("burn")).startswith("Fuel\n80.00/m\n(2× Refinery)")
    assert page.js(f"{edge('Plastic', 'burn')}.classes()") == ["byproduct", "used"]
    assert page.js(f"{edge('burn', 'generators')}.data('label')").startswith("66.67/m")

    page.select_node("generators")
    assert page.js(text("detail-buildings")) == "4× Fuel Generator, 3.33 fed"
    assert page.js(text("detail-power")) == "833.33 MW"
    for section in ("details-recipe-collapsible", "clock-controls"):
        assert page.js(f"document.getElementById('{section}').style.display") == "none"

    # The Refinery takes clocks like any node, but always runs Residual Fuel
    page.select_node("burn")
    assert page.js("document.getElementById('clock-controls').style.display") == ""
    assert page.js("document.getElementById('details-recipe-collapsible').style.display") == "none"
    assert page.js(text("detail-item")) == "Fuel"


def test_the_byproduct_button_burns_residue(page):
    page.open(page.base_url, PLASTIC)
    page.js(f"void {edge('Plastic', 'burn')}.emit('tap')")
    assert page.js("document.getElementById('byproduct-details').style.display") == "block"
    assert page.js(text("byproduct-sunk-label")) == "Burned for power:"
    assert page.js(text("byproduct-sunk")) == "100.00/min"
    assert page.js(text("byproduct-used")) == "0.00/min"
    assert page.js(text("byproduct-toggle-btn")) == "Use as Supply"
    assert "can't be sunk" not in page.js(text("byproduct-hint"))

    page.js("document.getElementById('byproduct-toggle-btn').click()")
    page.wait_until(f"({SAVED}.byproducts || {{}}).Plastic === 'use'")
    page.wait_until("document.getElementById('byproduct-toggle-btn').textContent === 'Burn for Power'")
    assert "is burned for power" in page.js(text("byproduct-hint"))  # nothing in this plan takes it
