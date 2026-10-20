"""Browser tests of fitting the last building's clock to the demand (ticket 047; see conftest.py)."""
import json

import pytest

SAVED = "JSON.parse(localStorage.getItem('sf_logistics_state'))"


def fit(page, need, scale=None):
    data = {"ideal_building_scale": need, "building_scale": scale if scale is not None else -(-need // 1)}
    return page.js(f"import('/static/js/panel.js').then(p => p.fitLastClock({json.dumps(data)}))")


@pytest.mark.parametrize("need, count, clock", [
    (4.3, 4, 1.3),       # one fewer, last at 130% (1 shard)
    (1.2, 1, 1.2),
    (3.6, 4, 0.6),       # one fewer needs 160%: the last underclocked instead
    (5.3, 6, 0.3),       # one fewer would be 5: underclocked
    (7.2, 8, 0.2),       # one fewer would be 7: underclocked
    (4.8, 4, 1.8),       # 5 avoided: 4 with 2 shards
    (6.9, 6, 1.9),       # 7 avoided: 6 with 2 shards
    (6.3, 6, 1.3),       # one fewer than 7, last at 130%
    (0.4, 1, 0.4),
    (2 / 3, 1, 0.666667),  # rounded up to 4 decimals of a percent
])
def test_fit_rule(page, need, count, clock):
    page.open(page.base_url)
    result = fit(page, need)
    assert result["count"] == count
    assert result["clock"] == pytest.approx(clock, abs=1e-6)
    assert result["clock"] >= need - (count - 1) - 1e-12  # never short
    assert result["groups"] == [{"clock": 1}, {"count": 1, "clock": result["clock"]}]


def test_nothing_to_fit(page):
    page.open(page.base_url)
    assert fit(page, 3, 3)["why"] == "No surplus to fit."
    assert fit(page, 5.005)["count"] == 5  # 6 with the last under 1%: 5, just over 100%


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
