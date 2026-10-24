"""Browser tests of Make from a by-product (ticket 059; see conftest.py). The branch is unit-tested in tests/unit/test_make_from_byproduct.py."""
import json

SAVED = "JSON.parse(localStorage.getItem('sf_logistics_state'))"
NITRO = {"items": ["Rocket Fuel"], "rates": [100], "clocks": {}, "merges": {},
         "recipes": {"Rocket Fuel": "Alternate: Nitro Rocket Fuel"}}
CY = "document.getElementById('cy')._cyreg.cy"
EDGES = rf"(globalThis.end = n => n.id().replace(/\|(in|out)$/, ''), {CY}.edges())"
RESIN = "Rocket Fuel__Fuel|Polymer Resin"
BRANCH = "Rocket Fuel__Fuel~Polymer Resin"


def edge(source, target):
    return f"{EDGES}.filter(e => end(e.source()) === {json.dumps(source)} && end(e.target()) === {json.dumps(target)})"


def choose(element_id, value):
    return f"""(() => {{
        const select = document.getElementById({json.dumps(element_id)});
        select.value = {json.dumps(value)};
        select.dispatchEvent(new Event('change'));
    }})()"""


def test_make_plastic_from_resin(page):
    page.open(page.base_url, NITRO)
    page.js(f"void {edge('Rocket Fuel__Fuel', 'sink')}.emit('tap')")
    assert page.js("document.getElementById('byproduct-item').textContent") == "Polymer Resin"
    page.wait_until("document.getElementById('byproduct-make').options.length === 4")
    assert page.js("document.getElementById('byproduct-make-to').disabled")

    page.js(choose("byproduct-make", "Residual Plastic"))
    page.wait_until(f"{CY}.getElementById({json.dumps(BRANCH)}).length > 0")
    saved = page.saved_plan()
    assert saved["byproducts"][RESIN] == {"choice": "make", "recipe": "Residual Plastic", "to": "supply"}
    assert saved["made"] == [{"item": "Plastic", "rate": 30, "from": RESIN}]
    assert page.js(f"{CY}.getElementById('demand|Plastic').data('label')") == "Plastic\n30.00/m\n(supply)"
    page.wait_until("document.getElementById('byproduct-make').value === 'Residual Plastic'")
    assert not page.js("document.getElementById('byproduct-make-to').disabled")

    # To the Sink: no supply circle, an edge to the Sink
    page.js(choose("byproduct-make-to", "sink"))
    page.wait_until(f"{SAVED}.byproducts[{json.dumps(RESIN)}].to === 'sink'")
    page.wait_until(f"{CY}.getElementById('demand|Plastic').length === 0")
    assert page.saved_plan()["made"] == []
    assert page.js(f"{edge(BRANCH, 'sink')}.length") == 1

    # The branch's node: recipe and clocks come from the by-product
    page.select_node(BRANCH)
    assert page.js("document.getElementById('details-recipe-collapsible').style.display") == "none"
    assert page.js("document.getElementById('clock-controls').style.display") == "none"

    # Nothing: back to the Sink, and the choice is gone
    page.js(f"void {edge('Rocket Fuel__Fuel', BRANCH)}.emit('tap')")
    page.wait_until("document.getElementById('byproduct-make').value === 'Residual Plastic'")
    page.js(choose("byproduct-make", ""))
    page.wait_until(f"{CY}.getElementById({json.dumps(BRANCH)}).length === 0")
    assert RESIN not in page.saved_plan()["byproducts"]
