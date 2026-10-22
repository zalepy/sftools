"""
Browser tests of fitting the last building's clock to the demand (ticket 047; see conftest.py). The rule
itself (which count, which clock) is unit-tested in tests/js/clocks.test.mjs.
"""
SAVED = "JSON.parse(localStorage.getItem('sf_logistics_state'))"


def test_fit_button_applies_and_undo_reverts(page):
    page.open(page.base_url, {"items": ["Smart Plating"], "rates": [13], "clocks": {}, "merges": {}, "recipes": {}})
    page.select_node("Smart Plating")
    button = "document.getElementById('fit-clock-btn')"
    assert not page.js(f"{button}.disabled")
    assert "6 buildings, the last at 150%" in page.js(f"{button}.title")
    page.js(f"{button}.click()")
    page.wait_until(f"{SAVED}.clocks['Smart Plating']")
    assert page.saved_plan()["clocks"]["Smart Plating"] == [{"clock": 1}, {"count": 1, "clock": 1.5}]
    page.wait_until("document.getElementById('clock-last').value === '150'")
    assert page.js("document.getElementById('detail-buildings').textContent").startswith("6")
    page.wait_until(f"{button}.disabled")
    assert page.js(f"{button}.title") == "No surplus to fit."

    page.js("document.getElementById('undo-btn').click()")
    page.wait_until(f"!{SAVED}.clocks['Smart Plating']")
    page.wait_until(f"!{button}.disabled")
