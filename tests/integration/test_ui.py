"""Browser tests of the planner UI (see conftest.py for the server and browser fixtures)."""
import json

import pytest

RIP_SP = "Smart Plating__Reinforced Iron Plate"
RIP_MF = "Modular Frame__Reinforced Iron Plate"
TWO_ROOTS = {"items": ["Smart Plating", "Modular Frame"], "rates": [2, 2], "roundUp": True,
             "overrides": {}, "merges": {}, "recipes": {}}


def plan(**changes):
    return {**TWO_ROOTS, **changes}


def label(node_id):
    return f"document.getElementById('cy')._cyreg.cy.getElementById({json.dumps(node_id)}).data('label')"


def switch_recipe(page, node_id, recipe):
    page.select_node(node_id)
    page.wait_until("!document.getElementById('recipe-select').disabled")
    page.js(f"""(() => {{
        const select = document.getElementById('recipe-select');
        select.value = {json.dumps(recipe)};
        select.dispatchEvent(new Event('change'));
    }})()""")
    page.wait_until(f"document.getElementById('detail-recipe').textContent === {json.dumps(recipe)}")


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
    assert f"{RIP_SP}__Screws" in page.node_ids()  # Bolted uses Screws too: same node
    assert page.js(label(RIP_SP)).startswith("Reinforced Iron Plate (A)\n")
    assert page.js(label(RIP_MF)).startswith("Reinforced Iron Plate\n")


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


def test_edges_show_what_each_supplier_provides(page):
    """A merged plate line needs 60 Screws/min: 24 from the Smart Plating branch, 36 from Modular Frame."""
    page.open(page.base_url, plan(merges={RIP_MF: RIP_SP}))
    labels = page.js(f"""document.getElementById('cy')._cyreg.cy.edges('[target = {json.dumps(json.dumps(RIP_SP))[1:-1]}]')
        .map(e => [e.source().id(), e.data('label')])""")
    assert dict(labels)[f"{RIP_SP}__Screws"] == "24.00/m"
    assert dict(labels)[f"{RIP_MF}__Screws"] == "36.00/m"


def test_selecting_a_node_keeps_its_color(page):
    page.open(page.base_url, plan(overrides={RIP_SP: 2}))
    node = f"document.getElementById('cy')._cyreg.cy.getElementById({json.dumps(RIP_SP)})"
    before = page.js(f"{node}.style('background-color')")
    page.js(f"void {node}.select()")
    assert page.js(f"{node}.style('background-color')") == before
    assert page.js(f"{node}.style('border-color')") == "rgb(244,63,94)"  # selected, even with an override


SP_SCREWS = f"{RIP_SP}__Screws"
ROTOR_ROD = "Smart Plating__Rotor__Iron Rod"


def test_switching_a_merged_node_leaves_no_old_inputs(page):
    page.open(page.base_url, plan(merges={f"{RIP_MF}__Screws": SP_SCREWS}))
    switch_recipe(page, SP_SCREWS, "Alternate: Cast Screws")
    ids = page.node_ids()
    assert f"{SP_SCREWS}__Iron Ingot" in ids
    assert not [i for i in ids if i.startswith((SP_SCREWS, f"{RIP_MF}__Screws")) and i.endswith("Iron Rod")]
    assert page.js(label(SP_SCREWS)).startswith("Screws (A)")
    assert page.js("document.getElementById('plan-notice').hidden")


def test_switching_away_and_back_starts_a_fresh_branch(page):
    """A merged Iron Rod keeps its other demand; the Screws branch's Iron Rod comes back unmerged."""
    sp_rod = f"{SP_SCREWS}__Iron Rod"
    page.open(page.base_url, plan(merges={sp_rod: ROTOR_ROD}, overrides={f"{sp_rod}__Iron Ingot": 2}))
    switch_recipe(page, SP_SCREWS, "Alternate: Cast Screws")
    assert page.saved_plan()["merges"] == {}
    assert page.saved_plan()["overrides"] == {}
    assert page.js("document.getElementById('plan-notice').hidden")  # dropped quietly

    switch_recipe(page, SP_SCREWS, "Screws")
    assert sp_rod in page.node_ids()  # back, on its own
    assert page.saved_plan()["merges"] == {}


def test_side_panel_collapses_and_the_graph_takes_the_room(page):
    page.open(page.base_url, plan())
    graph_width = "document.getElementById('cy')._cyreg.cy.width()"
    sidebar_shown = "getComputedStyle(document.getElementById('sidebar')).display !== 'none'"
    before = page.js(graph_width)
    assert page.js(sidebar_shown)

    page.js("document.getElementById('panel-toggle').click()")
    assert not page.js(sidebar_shown)
    assert page.js(graph_width) > before + 300  # the 350px panel is gone
    assert page.js("document.getElementById('panel-toggle').getAttribute('aria-expanded')") == "false"

    # Remembered in this browser
    page.send("Page.reload")
    page.wait(0.3)
    page.wait_until("document.readyState === 'complete' && document.querySelectorAll('.color-input').length > 0")
    assert not page.js(sidebar_shown)

    page.js("document.getElementById('panel-toggle').click()")
    assert page.js(sidebar_shown)
    assert page.js(graph_width) == before
