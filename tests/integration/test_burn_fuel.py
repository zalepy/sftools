"""Browser tests of burning fuel by-products (ticket 058; see conftest.py). The rule is unit-tested in tests/unit/test_burn_fuel.py."""
import json

SAVED = "JSON.parse(localStorage.getItem('sf_logistics_state'))"
NITRO = {"items": ["Rocket Fuel"], "rates": [100], "clocks": {}, "merges": {},
         "recipes": {"Rocket Fuel": "Alternate: Nitro Rocket Fuel"}}
CY = "document.getElementById('cy')._cyreg.cy"
EDGES = rf"(globalThis.end = n => n.id().replace(/\|(in|out)$/, ''), {CY}.edges())"


def edge(source, target):
    return f"{EDGES}.filter(e => end(e.source()) === {json.dumps(source)} && end(e.target()) === {json.dumps(target)})"


def text(element_id):
    return f"document.getElementById({json.dumps(element_id)}).textContent"


def click(element_id):
    return f"document.getElementById({json.dumps(element_id)}).click()"


def test_a_solid_fuel_is_burned_or_sent_to_the_sink(page):
    page.open(page.base_url, NITRO)
    assert page.js(f"{edge('Rocket Fuel', 'coal-generators')}.data('label')").startswith("25.00/m Compacted Coal")
    assert "Water" in page.node_ids()

    page.js(f"void {edge('Rocket Fuel', 'coal-generators')}.emit('tap')")
    assert page.js(text("byproduct-sunk-label")) == "Burned for power:"
    assert page.js(text("byproduct-sunk")) == "25.00/min"
    assert page.js(text("byproduct-toggle-btn")) == "Use as Supply"
    assert page.js(text("byproduct-sink-btn")) == "Send to Sink"

    # For a while, e.g. until the water is routed in
    page.js(click("byproduct-sink-btn"))
    page.wait_until(f"({SAVED}.byproducts || {{}})['Rocket Fuel'] === 'sink'")
    page.wait_until(f"{CY}.getElementById('coal-generators').length === 0")
    assert "Water" not in page.node_ids()
    page.wait_until("document.getElementById('byproduct-sink-btn').textContent === 'Burn for Power'")
    assert page.js(text("byproduct-sunk-label")) == "To the Sink:"
    assert "only for a while" in page.js(text("byproduct-hint"))

    page.js(click("byproduct-sink-btn"))
    page.wait_until(f"({SAVED}.byproducts || {{}})['Rocket Fuel'] === 'burn'")
    page.wait_until(f"{CY}.getElementById('coal-generators').length > 0")
    assert page.js(text("byproduct-sink-btn")) == "Send to Sink"


def test_a_fluid_fuel_has_no_sink_button(page):
    page.open(page.base_url, {**NITRO, "items": ["Fabric"], "rates": [30],
                              "recipes": {"Fabric": "Alternate: Polyester Fabric", "Fabric__Polymer Resin": "Fuel"}})
    page.js(f"void {edge('Fabric__Polymer Resin', 'generators')}.emit('tap')")
    assert page.js(text("byproduct-sunk-label")) == "Burned for power:"
    assert page.js("document.getElementById('byproduct-sink-btn').style.display") == "none"
