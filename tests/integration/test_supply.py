"""
Browser tests of supply-driven power plans (ticket 057; see conftest.py). The calculation is unit-tested in
tests/unit/test_supply.py, the texts and the Chain tab's rule in tests/js/supply-info.test.mjs.
"""
import json

SAVED = "JSON.parse(localStorage.getItem('sf_logistics_state'))"
FUEL = {"items": ["Fuel"], "rates": [1], "inbound": [{"item": "Crude Oil", "rate": 300}],
        "clocks": {}, "merges": {}, "recipes": {}}
CY = "document.getElementById('cy')._cyreg.cy"


def text(element_id):
    return f"document.getElementById({json.dumps(element_id)}).textContent"


def shown(element_id):
    return f"document.getElementById({json.dumps(element_id)}).style.display !== 'none'"


def test_the_inbound_limits_a_fuel_plan(page):
    page.open(page.base_url, FUEL)
    # Offered, not on: the plan makes the 1 Fuel asked
    assert page.js(shown("supply-limit-group")) and not page.js("document.getElementById('supply-limit').checked")
    assert not page.js(shown("supply-summary"))
    assert "demand|Fuel" in page.node_ids() and "generators" not in page.node_ids()

    page.js("document.getElementById('supply-limit').click()")
    page.wait_until(f"{CY}.getElementById('generators').length > 0")
    assert page.saved_plan()["supplyLimit"] is True
    page.wait_until(shown("supply-summary"))
    assert page.js(text("supply-summary")).startswith("Limited by Crude Oil · 2,500 MW gross / ")
    assert "Fuel: 200.00/min burned" in page.js(text("supply-summary"))
    assert "demand|Fuel" not in page.node_ids() and "inbound:Crude Oil" not in page.node_ids()
    # Edges end at the logistics sides ('Fuel|out' to 'generators|in')
    end = r"(n => n.id().replace(/\|(in|out)$/, ''))"
    assert page.js(f"{CY}.edges().filter(e => {end}(e.source()) === 'Fuel' && {end}(e.target()) === 'generators').length") == 1

    page.select_node("generators")
    assert page.js(text("detail-buildings")) == "10× Fuel Generator, 10.00 fed"
    assert page.js(text("detail-output-rate")) == "200.00/min Fuel burned"

    page.js("document.getElementById('undo-btn').click()")
    page.wait_until(f"{CY}.getElementById('generators').length === 0")
    assert not page.js("document.getElementById('supply-limit').checked")
    assert not page.js(shown("supply-summary"))


def test_the_limit_is_offered_only_for_fuels(page):
    page.open(page.base_url, {**FUEL, "supplyLimit": True})
    page.wait_until(shown("supply-summary"))
    # A non-fuel demand: no checkbox, no summary (the saved choice stays for when the rule holds again)
    page.js("""(() => {
        const input = document.querySelector('#demand-rows input[name=items]');
        input.value = 'Plastic';
        input.dispatchEvent(new Event('input', { bubbles: true }));
    })()""")
    assert not page.js(shown("supply-limit-group")) and not page.js(shown("supply-summary"))
    page.js("document.getElementById('demand-form').requestSubmit()")
    page.wait_until(f"{CY}.getElementById('demand|Plastic').length > 0")
    assert "inbound:Crude Oil" in page.node_ids()  # a plain plan again: the crude is inbound production


def test_nuclear_waste_can_t_be_sunk(page):
    page.open(page.base_url, {**FUEL, "items": ["Uranium Fuel Rod"], "inbound": [{"item": "Uranium", "rate": 100}],
                              "supplyLimit": True})
    page.wait_until(f"{CY}.getElementById('nuclear-plants').length > 0")
    assert page.js(f"{CY}.getElementById('sink').data('label')").endswith("fluids can't be sunk!")  # Sulfuric Acid too
    page.select_node("sink")
    assert "Nuclear waste can't be sunk: Uranium Waste" in page.js(text("detail-surplus-value"))
