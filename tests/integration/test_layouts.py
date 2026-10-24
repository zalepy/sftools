"""Browser tests of the reference layouts drawer (ticket 056; see conftest.py). Its numbers are checked in tests/unit/test_layouts.py."""
PLAN = {"items": ["Smart Plating"], "rates": [2], "clocks": {}, "merges": {}, "recipes": {}}


def hidden(element_id):
    return f"document.getElementById('{element_id}').hidden"


def click(element_id):
    return f"document.getElementById('{element_id}').click()"


def test_layouts_drawer(page):
    page.open(page.base_url, PLAN)
    page.js(click("layouts-toggle"))
    page.wait_until("Boolean(document.querySelector('#layouts-content .layout-svg'))")
    assert not page.js(hidden("layouts"))
    assert page.js("document.querySelector('#layouts-content h2').textContent") == "Crude Oil to Turbofuel power"
    assert page.js("document.querySelectorAll('#layouts-content .layout-building').length") == 63
    assert page.js("document.querySelectorAll('#layouts-content .layout-table tbody tr').length") == 5
    assert page.js("document.querySelector('#layouts-content .layout-power').textContent").startswith("Power used: 3,097 MW")
    title = "document.querySelector('#layouts-content .layout-building title').textContent"
    assert page.js(title) == "Refinery 21: Fuel at 83.334%, into the green Fuel pipe"
    # The drawing fits the drawer: no sideways scrolling
    assert page.js("(d => d.scrollWidth <= d.clientWidth)(document.querySelector('#layouts-content .layout-drawing'))")

    # The legend, the guide and the layouts close each other
    page.js(click("legend-toggle"))
    assert page.js(hidden("layouts")) and not page.js(hidden("legend"))
    page.js(click("layouts-toggle"))
    assert page.js(hidden("legend")) and not page.js(hidden("layouts"))
    page.js(click("guide-toggle"))
    assert page.js(hidden("layouts")) and not page.js(hidden("guide"))
    page.js(click("layouts-toggle"))
    assert page.js(hidden("guide")) and not page.js(hidden("layouts"))
    page.js(click("layouts-close"))
    assert page.js(hidden("layouts"))
