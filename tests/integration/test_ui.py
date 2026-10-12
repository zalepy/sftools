"""Browser tests of the planner UI (see conftest.py for the server and browser fixtures)."""
import json

import pytest

RIP_SP = "Smart Plating__Reinforced Iron Plate"
RIP_MF = "Modular Frame__Reinforced Iron Plate"
TWO_ROOTS = {"items": ["Smart Plating", "Modular Frame"], "rates": [2, 2], "roundUp": True,
             "overrides": {}, "merges": {}, "recipes": {}}


def plan(**changes):
    return {**TWO_ROOTS, **changes}


def test_page_loads(page):
    page.open(page.base_url)
    assert page.js("document.querySelectorAll('[onclick],[onsubmit],[onchange]').length") == 0
    assert page.js("document.querySelectorAll('#items_list option').length") > 100
    assert page.saved_plan() is None


def test_calculate_from_the_form_saves_the_plan(page):
    page.open(page.base_url)
    page.js("""(() => {
        const inputs = document.querySelectorAll('#demand-rows .demand-row input');
        inputs[0].value = 'Smart Plating';
        inputs[1].value = '2';
        document.getElementById('demand-form').requestSubmit();
    })()""")
    page.wait_until("localStorage.getItem('sf_planner_state') !== null")
    assert page.saved_plan()["items"] == ["Smart Plating"]
    assert "Smart Plating" in page.node_ids()


def test_demand_rows_can_be_added_and_removed(page):
    page.open(page.base_url)
    rows = "document.querySelectorAll('#demand-rows .demand-row').length"
    page.js("document.getElementById('add-row-btn').click()")
    assert page.js(rows) == 2
    page.js("document.querySelectorAll('#demand-rows .remove-row')[1].click()")
    assert page.js(rows) == 1
    page.js("document.querySelector('#demand-rows input').value = 'x'; document.querySelector('.remove-row').click()")
    assert page.js(rows) == 1  # the last row is only cleared
    assert page.js("document.querySelector('#demand-rows input').value") == ""


def test_node_details_and_derivation(page):
    page.open(page.base_url, plan())
    page.select_node(f"{RIP_SP}__Screws")
    assert page.js("document.getElementById('node-details').style.display") == "block"
    assert page.js("document.getElementById('detail-item').textContent") == "Screws"
    assert page.js("[...document.querySelectorAll('#detail-derivation .item')].map(e => e.textContent)") == [
        "Smart Plating", "Reinforced Iron Plate", "Screws"]
    assert page.js("document.querySelectorAll('#detail-inputs-container details').length") == 1
    page.wait_until("document.getElementById('recipe-select').options.length > 1")


def test_recipe_switch(page):
    page.open(page.base_url, plan())
    page.select_node(RIP_SP)
    page.wait_until("!document.getElementById('recipe-select').disabled")
    page.js("""(() => {
        const select = document.getElementById('recipe-select');
        select.value = 'Alternate: Bolted Iron Plate';
        select.dispatchEvent(new Event('change'));
    })()""")
    page.wait_until("document.getElementById('detail-recipe').textContent === 'Alternate: Bolted Iron Plate'")
    assert page.saved_plan()["recipes"] == {RIP_SP: "Alternate: Bolted Iron Plate"}
    assert f"{RIP_SP}__Alternate: Bolted Iron Plate>Screws" in page.node_ids()


def test_override_apply_and_clear(page):
    page.open(page.base_url, plan())
    page.select_node(RIP_SP)
    page.js("document.getElementById('override-scale').value = '3'; document.getElementById('apply-override-btn').click()")
    page.wait_until(f"JSON.parse(localStorage.getItem('sf_planner_state')).overrides[{json.dumps(RIP_SP)}] === 3")
    page.select_node(RIP_SP)
    assert page.js("document.getElementById('detail-scale').textContent") == "3.00x"

    page.js("document.getElementById('clear-override-btn').click()")
    page.wait_until("Object.keys(JSON.parse(localStorage.getItem('sf_planner_state')).overrides).length === 0")


def test_merge_by_drag_and_unmerge(page):
    page.open(page.base_url, plan())
    page.drag(page.node_position(RIP_MF), page.node_position(RIP_SP))
    page.wait_until(f"JSON.parse(localStorage.getItem('sf_planner_state')).merges[{json.dumps(RIP_MF)}] !== undefined")
    assert page.saved_plan()["merges"] == {RIP_MF: RIP_SP}
    assert RIP_MF not in page.node_ids()
    assert page.js("document.getElementById('toast').hidden")  # same recipe: no warning

    page.select_node(RIP_SP)
    assert page.js("document.getElementById('unmerge-btn').style.display") == "block"
    assert page.js("document.querySelectorAll('#detail-merged .derivation').length") == 1
    page.js("document.getElementById('unmerge-btn').click()")
    page.wait_until("Object.keys(JSON.parse(localStorage.getItem('sf_planner_state')).merges).length === 0")
    assert RIP_MF in page.node_ids()


def test_merging_different_recipes_shows_a_brief_warning(page):
    page.open(page.base_url, plan(recipes={RIP_MF: "Alternate: Bolted Iron Plate"}))
    page.drag(page.node_position(RIP_MF), page.node_position(RIP_SP))
    page.wait_until("!document.getElementById('toast').hidden")
    assert "different recipes" in page.js("document.getElementById('toast').textContent")
    page.wait_until("document.getElementById('toast').hidden", timeout=8)


def test_stale_saved_entries_are_dropped_with_a_notice(page):
    page.open(page.base_url, plan(overrides={"root__Gone": 2}))
    page.wait_until("!document.getElementById('plan-notice').hidden")
    assert "no longer match" in page.js("document.querySelector('#plan-notice .plan-notice-text').textContent")
    assert page.saved_plan()["overrides"] == {}
    page.js("document.querySelector('#plan-notice .close').click()")
    assert page.js("document.getElementById('plan-notice').hidden")


def test_colors_are_saved_in_the_browser(page):
    page.open(page.base_url)
    page.js("document.querySelector('.tab[data-tab=colors]').click()")
    assert page.js("document.getElementById('colors-tab').classList.contains('active')")
    item = page.js("document.querySelector('.color-input').dataset.item")
    page.js("document.querySelector('.color-input').value = '#123456'; document.getElementById('save-colors-btn').click()")
    page.wait_until("localStorage.getItem('sf_planner_colors') !== null")
    assert page.js(f"JSON.parse(localStorage.getItem('sf_planner_colors'))[{json.dumps(item)}]") == "#123456"
    assert page.dialogs == ["Colors saved in this browser."]


def test_split_set_parts_and_unsplit(page):
    page.open(page.base_url, plan())
    page.select_node(RIP_SP)
    assert page.js("document.getElementById('split-btn').textContent") == "Split"
    page.js("document.getElementById('split-count').value = '3'; document.getElementById('split-btn').click()")
    page.wait_until(f"JSON.parse(localStorage.getItem('sf_planner_state')).splits[{json.dumps(RIP_SP)}] === 3")
    assert {f"{RIP_SP}~2", f"{RIP_SP}~3", f"{RIP_SP}~3__Screws"} <= set(page.node_ids())
    assert page.js(f"document.getElementById('cy')._cyreg.cy.getElementById({json.dumps(RIP_SP + '~3')}).data('label')"
                   ).startswith("Reinforced Iron Plate [3/3]")

    # A part has its own override; reducing the number of parts drops what belonged to removed parts
    page.select_node(f"{RIP_SP}~3")
    assert "Part 3 of 3" in page.js("document.getElementById('split-hint').textContent")
    page.js("document.getElementById('override-scale').value = '2'; document.getElementById('apply-override-btn').click()")
    page.wait_until(f"JSON.parse(localStorage.getItem('sf_planner_state')).overrides[{json.dumps(RIP_SP + '~3')}] === 2")
    page.select_node(f"{RIP_SP}~2")
    page.js("document.getElementById('split-count').value = '2'; document.getElementById('split-btn').click()")
    page.wait_until(f"JSON.parse(localStorage.getItem('sf_planner_state')).splits[{json.dumps(RIP_SP)}] === 2")
    assert page.saved_plan()["overrides"] == {}
    assert f"{RIP_SP}~3" not in page.node_ids()
    assert page.js("document.getElementById('detail-id').textContent") == f"{RIP_SP}~2"

    page.js("document.getElementById('unsplit-btn').click()")
    page.wait_until("Object.keys(JSON.parse(localStorage.getItem('sf_planner_state')).splits).length === 0")
    assert f"{RIP_SP}~2" not in page.node_ids()
    assert page.js("document.getElementById('detail-id').textContent") == RIP_SP


def test_merged_node_cannot_be_split(page):
    page.open(page.base_url, plan(merges={RIP_MF: RIP_SP}))
    page.select_node(RIP_SP)
    assert page.js("document.getElementById('split-btn').disabled")
    assert "Unmerge first" in page.js("document.getElementById('split-hint').textContent")


def test_dragging_a_part_onto_another_merges_them(page):
    page.open(page.base_url, plan(splits={RIP_SP: 2}))
    page.drag(page.node_position(f"{RIP_SP}~2"), page.node_position(RIP_SP))
    page.wait_until(f"JSON.parse(localStorage.getItem('sf_planner_state')).merges[{json.dumps(RIP_SP + '~2')}] !== undefined")
    assert page.saved_plan()["merges"] == {f"{RIP_SP}~2": RIP_SP}


def test_mouse_wheel_zooms_in_small_steps(page):
    page.open(page.base_url, plan())
    page.wait(1)  # layout and fit
    zoom = "document.getElementById('cy')._cyreg.cy.zoom()"
    before = page.js(zoom)
    x, y = page.node_position(RIP_SP)
    page.send("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=0, deltaY=-100)
    page.wait(0.3)
    after = page.js(zoom)
    assert 1.1 < after / before < 1.25  # one tick in
    page.send("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=0, deltaY=100)
    page.wait(0.3)
    assert page.js(zoom) == pytest.approx(before, rel=0.01)  # and back out
    assert abs(page.node_position(RIP_SP)[0] - x) < 2  # the point under the cursor stays put
