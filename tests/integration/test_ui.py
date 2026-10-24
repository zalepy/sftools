"""Browser tests of the planner UI (see conftest.py for the server and browser fixtures)."""
import json

import pytest

RIP_SP = "Smart Plating__Reinforced Iron Plate"
RIP_MF = "Modular Frame__Reinforced Iron Plate"
TWO_ROOTS = {"items": ["Smart Plating", "Modular Frame"], "rates": [2, 2],
             "clocks": {}, "merges": {}, "recipes": {}}
SAVED = "JSON.parse(localStorage.getItem('sf_logistics_state'))"


def plan(**changes):
    return {**TWO_ROOTS, **changes}


# The graph's edges, and the production node at an end of one: edges run between logistics nodes
# ('<id>|out' to '<id>|in')
EDGES = r"(globalThis.end = n => n.id().replace(/\|(in|out)$/, ''), document.getElementById('cy')._cyreg.cy.edges())"


def label(node_id):
    return f"document.getElementById('cy')._cyreg.cy.getElementById({json.dumps(node_id)}).data('label')"


def switch_recipe(page, node_id, recipe):
    page.select_node(node_id)
    # The node's recipes load from the server: wait for this one to be offered (the list may still hold the
    # previous node's recipes, and be enabled)
    page.wait_until(f"[...document.getElementById('recipe-select').options].some(o => o.value === {json.dumps(recipe)})")
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
    page.wait_until("localStorage.getItem('sf_logistics_state') !== null")
    assert page.saved_plan()["items"] == ["Smart Plating"]
    assert "Smart Plating" in page.node_ids()


def test_calculate_waits_for_startup(page):
    """
    Calculate before startup had loaded the tabs failed ("Calculation failed": no tab to save the plan in),
    seen on the slower live demo. Startup is held at a request it waits for; Calculate does nothing until then.
    """
    page.open(page.base_url)  # an empty plan, started up: nothing of it is saved or requested later
    page.hold_requests("*/api/power_items*")
    page.send("Page.reload")
    page.wait_until("document.readyState === 'complete' && document.querySelectorAll('.color-input').length > 0")
    for _ in range(100):  # startup reaches the held request
        if page.paused:
            break
        page.wait(0.05)
    assert page.paused
    page.js("""(() => {
        const inputs = document.querySelectorAll('#demand-rows .demand-row input');
        inputs[0].value = 'Smart Plating';
        inputs[1].value = '2';
        document.getElementById('demand-form').requestSubmit();
    })()""")
    page.wait(0.5)
    assert page.dialogs == [] and page.js("localStorage.getItem('sf_logistics_state')") is None
    assert page.js("document.getElementById('calculate-btn').disabled")

    page.release_requests()
    page.wait_until("!document.getElementById('calculate-btn').disabled")
    page.js("""(() => {
        const inputs = document.querySelectorAll('#demand-rows .demand-row input');
        inputs[0].value = 'Smart Plating';
        inputs[1].value = '2';
        document.getElementById('demand-form').requestSubmit();
    })()""")
    page.wait_until("localStorage.getItem('sf_logistics_state') !== null")
    assert page.saved_plan()["items"] == ["Smart Plating"] and page.dialogs == []


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


def test_clocks_apply_and_clear(page):
    """144 Iron Rod: 10 x 100% by default; with the last building at 200%, 9 buildings."""
    page.open(page.base_url, plan(items=["Iron Rod"], rates=[144]))
    assert page.js("document.getElementById('round-up-toggle')") is None
    assert page.js("document.getElementById('override-scale')") is None
    assert "(10× Constructor)" in page.js(label("Iron Rod"))

    page.select_node("Iron Rod")
    page.js("document.getElementById('clock-last').value = '200'; document.getElementById('apply-clocks-btn').click()")
    page.wait_until(f"{SAVED}.clocks['Iron Rod'] !== undefined")
    assert page.saved_plan()["clocks"] == {"Iron Rod": [{"clock": 1}, {"count": 1, "clock": 2}]}
    assert page.js(label("Iron Rod")).endswith("(9× Constructor)\n8×100% + 1×200%\n2 shards")
    assert page.js("document.getElementById('detail-buildings').textContent") == "9 (8 × 100% + 1 × 200%)"
    assert page.js("document.getElementById('clock-last').value") == "200"

    page.js("document.getElementById('clear-clocks-node-btn').click()")
    page.wait_until(f"Object.keys({SAVED}.clocks).length === 0")
    assert page.js(label("Iron Rod")).endswith("(10× Constructor)")


def test_old_plans_with_building_overrides_still_load(page):
    """Plans saved before clock speeds have an 'overrides' key; it is ignored and gone once the plan is saved."""
    page.open(page.base_url, plan(overrides={RIP_SP: 3}, roundUp=False))
    page.wait_until(f"{SAVED}.clocks !== undefined")
    assert "overrides" not in page.saved_plan()
    assert "roundUp" not in page.saved_plan()
    assert page.js("document.getElementById('plan-notice').hidden")


def test_merge_by_drag_and_unmerge(page):
    page.open(page.base_url, plan())
    page.drag(page.node_position(RIP_MF), page.node_position(RIP_SP))
    page.wait_until(f"JSON.parse(localStorage.getItem('sf_logistics_state')).merges[{json.dumps(RIP_MF)}] !== undefined")
    assert page.saved_plan()["merges"] == {RIP_MF: RIP_SP}
    assert RIP_MF not in page.node_ids()
    assert page.js("document.getElementById('toast').hidden")  # same recipe: no warning

    page.select_node(RIP_SP)
    assert page.js("document.getElementById('unmerge-btn').style.display") == "block"
    assert page.js("document.querySelectorAll('#detail-merged .derivation').length") == 1
    page.js("document.getElementById('unmerge-btn').click()")
    page.wait_until("Object.keys(JSON.parse(localStorage.getItem('sf_logistics_state')).merges).length === 0")
    assert RIP_MF in page.node_ids()


def test_merging_different_recipes_shows_a_brief_warning(page):
    page.open(page.base_url, plan(recipes={RIP_MF: "Alternate: Bolted Iron Plate"}))
    page.drag(page.node_position(RIP_MF), page.node_position(RIP_SP))
    page.wait_until("!document.getElementById('toast').hidden")
    assert "different recipes" in page.js("document.getElementById('toast').textContent")
    page.wait_until("document.getElementById('toast').hidden", timeout=8)


def test_stale_saved_entries_are_dropped_with_a_notice(page):
    page.open(page.base_url, plan(clocks={"root__Gone": [{"clock": 2}]}))
    page.wait_until("!document.getElementById('plan-notice').hidden")
    assert "no longer match" in page.js("document.querySelector('#plan-notice .plan-notice-text').textContent")
    assert page.saved_plan()["clocks"] == {}
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


def color_of(page, item):
    return page.js(f"[...document.querySelectorAll('#color-list .color-input')].find(i => i.dataset.item === {json.dumps(item)})?.value ?? null")


def test_defining_colors(page):
    """Define adds an item's color (ticket 044); × removes it, or resets a built-in one; Save keeps it."""
    page.open(page.base_url, plan())
    page.js("document.querySelector('.tab[data-tab=colors]').click()")
    rotor = "Smart Plating__Rotor"
    before = page.js(node_style(rotor, "background-color"))

    page.js("document.getElementById('color-add-item').value = 'Rotorr'; document.getElementById('color-add-btn').click()")
    assert page.js("document.getElementById('color-add-error').textContent") == "Unknown item: Rotorr"
    assert color_of(page, "Rotorr") is None

    page.js("""(() => {
        document.getElementById('color-add-item').value = 'Rotor';
        document.getElementById('color-add-value').value = '#ab1234';
        document.getElementById('color-add-btn').click();
    })()""")
    assert page.js("document.getElementById('color-add-error').hidden")
    assert color_of(page, "Rotor") == "#ab1234"
    assert page.js(node_style(rotor, "background-color")) == before  # not until saved
    page.js("document.getElementById('save-colors-btn').click()")
    page.wait_until(f"{node_style(rotor, 'background-color')} === 'rgb(171,18,52)'")
    assert page.js("JSON.parse(localStorage.getItem('sf_planner_colors'))")["Rotor"] == "#ab1234"

    # × on a built-in item resets it; on Rotor it drops the row
    page.js("""(() => {
        const input = [...document.querySelectorAll('#color-list .color-input')].find(i => i.dataset.item === 'Screws');
        input.value = '#000001';
        input.parentElement.querySelector('.color-remove').click();
    })()""")
    assert color_of(page, "Screws") == "#1e3a8a"
    page.js("""[...document.querySelectorAll('#color-list .color-item')].find(r => r.dataset.item === 'Rotor')
        .querySelector('.color-remove').click()""")
    assert color_of(page, "Rotor") is None
    page.js("document.getElementById('save-colors-btn').click()")
    page.wait_until(f"{node_style(rotor, 'background-color')} === {json.dumps(before)}")
    saved = page.js("JSON.parse(localStorage.getItem('sf_planner_colors'))")
    assert "Rotor" not in saved and saved["Screws"] == "#1e3a8a"


SCREWS = ["Smart Plating__Reinforced Iron Plate__Screws", "Smart Plating__Rotor__Screws",
          "Modular Frame__Reinforced Iron Plate__Screws"]
CAST = "Alternate: Cast Screws"


def recipes_of(node_ids):
    return f"import('/static/js/graph.js').then(g => {json.dumps(node_ids)}.map(id => g.getNodeData(id)?.recipe_name))"


def test_preferred_recipes(page):
    """Ticket 043: a recipe preferred for an item runs in every node of it that has no recipe of its own."""
    page.open(page.base_url, plan(merges={SCREWS[2]: SCREWS[1]}))
    shown = SCREWS[:2]
    switch_recipe(page, SCREWS[0], CAST)
    assert page.js("document.getElementById('prefer-btn').textContent") == "Prefer for Screws"
    page.js("document.getElementById('prefer-btn').click()")
    page.wait_until(f"{recipes_of(shown)}.then(r => r.every(name => name === {json.dumps(CAST)}))")
    # Kept in the browser for every tab, not in the plan; the node's own choice went (it's the preferred one)
    assert page.js("JSON.parse(localStorage.getItem('sf_planner_recipes'))") == {"Screws": CAST}
    assert page.saved_plan()["recipes"] == {}
    page.wait_until("document.getElementById('prefer-btn').style.display === 'none'")
    assert page.js("document.getElementById('preferred-hint').textContent").startswith("Preferred for Screws")

    # A node's own choice still wins
    switch_recipe(page, SCREWS[1], "Screws")
    assert page.js(recipes_of(shown)) == [CAST, "Screws"]

    # Unmerged: the node split back out keeps the merged node's recipe
    assert page.js("document.getElementById('unmerge-btn').style.display") == "block"
    page.js("document.getElementById('unmerge-btn').click()")
    page.wait_until(f"{recipes_of(SCREWS)}.then(r => r[2] === 'Screws')")
    assert page.saved_plan()["recipes"] == {SCREWS[1]: "Screws", SCREWS[2]: "Screws"}

    # The Recipes tab: every item with a choice, the changed ones highlighted; back to the default there
    page.js("document.querySelector('.tab[data-tab=recipes]').click()")
    row = "document.querySelector('.recipe-choice[data-item=Screws]')"
    assert page.js(f"{row}.classList.contains('changed') && {row}.querySelector('select').value") == CAST
    page.js("document.getElementById('recipe-changed-only').click()")
    assert page.js("[...document.querySelectorAll('.recipe-choice')].filter(r => !r.hidden).map(r => r.dataset.item)") == ["Screws"]
    page.js(f"(() => {{ const s = {row}.querySelector('select'); s.value = 'Screws'; s.dispatchEvent(new Event('change')); }})()")
    page.wait_until(f"{recipes_of(SCREWS)}.then(r => r[0] === 'Screws')")
    assert page.js("JSON.parse(localStorage.getItem('sf_planner_recipes'))") == {}
    assert not page.js(f"{row}.classList.contains('changed')")

    # Picked there for an item: Iron Rod from Steel Rods, everywhere
    page.js("document.getElementById('recipe-changed-only').click()")
    rod = "document.querySelector('.recipe-choice[data-item=\"Iron Rod\"] select')"
    page.js(f"(() => {{ const s = {rod}; s.value = 'Alternate: Steel Rod'; s.dispatchEvent(new Event('change')); }})()")
    page.wait_until("JSON.parse(localStorage.getItem('sf_planner_recipes'))['Iron Rod'] === 'Alternate: Steel Rod'")
    page.wait_until(f"{recipes_of(['Modular Frame__Iron Rod'])}.then(r => r[0] === 'Alternate: Steel Rod')")


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
    labels = page.js(f"""{EDGES}.filter(e => end(e.target()) === {json.dumps(RIP_SP)})
        .map(e => [end(e.source()), e.data('label')])""")
    assert dict(labels)[f"{RIP_SP}__Screws"].startswith("24.00/m")
    assert dict(labels)[f"{RIP_MF}__Screws"].startswith("36.00/m")


def test_selecting_a_node_keeps_its_color(page):
    page.open(page.base_url, plan(clocks={RIP_SP: [{"clock": 0.5}]}))
    node = f"document.getElementById('cy')._cyreg.cy.getElementById({json.dumps(RIP_SP)})"
    before = page.js(f"{node}.style('background-color')")
    page.js(f"void {node}.select()")
    assert page.js(f"{node}.style('background-color')") == before
    assert page.js(f"{node}.style('border-color')") == "rgb(244,63,94)"  # selected, even with clocks set


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
    page.open(page.base_url, plan(merges={sp_rod: ROTOR_ROD}, clocks={f"{sp_rod}__Iron Ingot": [{"clock": 0.5}]}))
    switch_recipe(page, SP_SCREWS, "Alternate: Cast Screws")
    assert page.saved_plan()["merges"] == {}
    assert page.saved_plan()["clocks"] == {}
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


def undo_state(page):
    return page.js("[document.getElementById('undo-btn').disabled, document.getElementById('redo-btn').disabled]")


def press_ctrl(page, key, shift=False):
    """A Ctrl+key press on the page (not in a text field)."""
    modifiers = 2 | (8 if shift else 0)
    code = f"Key{key.upper()}"
    for event in ("rawKeyDown", "keyUp"):
        page.send("Input.dispatchKeyEvent", type=event, modifiers=modifiers, key=key, code=code,
                  windowsVirtualKeyCode=ord(key.upper()))


def test_undo_and_redo_a_merge(page):
    page.open(page.base_url, plan())
    assert undo_state(page) == [True, True]  # nothing to undo yet

    page.drag(page.node_position(RIP_MF), page.node_position(RIP_SP))
    page.wait_until(f"{SAVED}.merges[{json.dumps(RIP_MF)}] !== undefined")
    assert undo_state(page) == [False, True]

    page.js("document.getElementById('undo-btn').click()")
    page.wait_until(f"Object.keys({SAVED}.merges).length === 0")
    page.wait_until(f"document.getElementById('cy')._cyreg.cy.getElementById({json.dumps(RIP_MF)}).length === 1")
    assert undo_state(page) == [True, False]

    page.js("document.getElementById('redo-btn').click()")
    page.wait_until(f"{SAVED}.merges[{json.dumps(RIP_MF)}] !== undefined")
    assert RIP_MF not in page.node_ids()
    assert undo_state(page) == [False, True]


def test_undo_with_the_keyboard_and_a_new_change_drops_redo(page):
    page.open(page.base_url, plan(items=["Iron Rod"], rates=[144]))
    page.select_node("Iron Rod")
    page.js("document.getElementById('clock-all').value = '50'; document.getElementById('apply-clocks-btn').click()")
    page.wait_until(f"{SAVED}.clocks['Iron Rod'] !== undefined")

    # Ctrl+Z while typing in a field edits the text, not the plan
    page.js("document.getElementById('clock-last').focus()")
    press_ctrl(page, "z")
    page.wait(0.3)
    assert page.saved_plan()["clocks"] != {}

    page.js("document.activeElement.blur()")
    press_ctrl(page, "z")
    page.wait_until(f"Object.keys({SAVED}.clocks).length === 0")
    press_ctrl(page, "z", shift=True)  # redo
    page.wait_until(f"{SAVED}.clocks['Iron Rod'] !== undefined")
    press_ctrl(page, "z")
    page.wait_until(f"Object.keys({SAVED}.clocks).length === 0")

    # A new change after undo replaces the step that could have been redone
    page.select_node("Iron Rod")
    page.js("document.getElementById('clock-all').value = '200'; document.getElementById('apply-clocks-btn').click()")
    page.wait_until(f"{SAVED}.clocks['Iron Rod'] !== undefined")
    assert undo_state(page) == [False, True]
    assert page.saved_plan()["clocks"]["Iron Rod"] == [{"clock": 2}]


def node_style(node_id, prop):
    return f"document.getElementById('cy')._cyreg.cy.getElementById({json.dumps(node_id)}).style('{prop}')"


BOOK = "JSON.parse(localStorage.getItem('sf_logistics_book'))"
ROTOR = "Smart Plating__Rotor"


def move_branch(page, node_id, destination):
    """Move Branch to Inbound on the node, to a destination: '' (Undefined), a tab name, or 'New tab'."""
    page.select_node(node_id)
    page.js("document.getElementById('move-branch-btn').click()")
    page.js(f"""(() => {{
        const select = document.getElementById('move-branch-dest');
        const option = [...select.options].find(o => {json.dumps(destination)} ? o.text.startsWith({json.dumps(destination)}) : o.value === '');
        select.value = option.value;
        select.dispatchEvent(new Event('change'));
        document.getElementById('move-branch-confirm').click();
    }})()""")


def test_move_branch_needs_a_single_node_that_is_not_a_demand_target(page):
    """Ticket 045: inbound production covers the item plan-wide, so the item must be made by one node."""
    page.open(page.base_url, plan())
    page.select_node(RIP_SP)
    assert page.js("document.getElementById('move-branch-btn').disabled")
    assert page.js("document.getElementById('move-branch-why').textContent") == "Merge all 2 Reinforced Iron Plate nodes first."
    page.select_node("Smart Plating")
    assert page.js("document.getElementById('move-branch-why').textContent") == "Smart Plating is a demand target of this plan."
    page.select_node(ROTOR)
    assert not page.js("document.getElementById('move-branch-btn').disabled")
    # "Supplied from outside" is gone from the recipes (superseded by this)
    page.wait_until("!document.getElementById('recipe-select').disabled")
    assert "Supplied from outside" not in page.js("[...document.getElementById('recipe-select').options].map(o => o.value)")


def test_move_branch_to_a_new_tab_then_to_an_existing_one(page):
    page.open(page.base_url, plan(merges={RIP_MF: RIP_SP}))
    move_branch(page, ROTOR, "New tab")
    page.wait_until(f"{SAVED}.inbound.length === 1")
    assert page.saved_plan()["inbound"] == [{"item": "Rotor", "rate": 2}]
    assert ROTOR not in page.node_ids() and "inbound:Rotor" in page.node_ids()
    book = page.js(BOOK)
    source, new = book["tabs"]
    assert book["active"] == source["id"]  # stays on the source plan
    assert (new["name"], new["plan"]["items"], new["plan"]["rates"]) == ("Rotor", ["Rotor"], [2])
    assert book["chain"]["links"] == [{"from": {"tab": new["id"], "item": "Rotor"}, "to": {"tab": source["id"], "item": "Rotor"}}]
    assert "Moved 2.00/min Rotor to Rotor." in page.js("document.body.innerText")

    # The merged plates (2 + 3) go to the same tab, as a second demand target
    move_branch(page, RIP_SP, "Rotor")
    page.wait_until(f"{SAVED}.inbound.length === 2")
    assert page.saved_plan()["inbound"][1] == {"item": "Reinforced Iron Plate", "rate": 5}
    new = page.js(BOOK)["tabs"][1]
    assert (new["plan"]["items"], new["plan"]["rates"]) == (["Rotor", "Reinforced Iron Plate"], [2, 5])
    assert len(page.js(BOOK)["chain"]["links"]) == 2


def test_move_branch_without_a_destination(page):
    page.open(page.base_url, plan())
    move_branch(page, ROTOR, "")
    page.wait_until(f"{SAVED}.inbound.length === 1")
    book = page.js(BOOK)
    assert len(book["tabs"]) == 1 and book["chain"]["links"] == []
    assert "Moved 2.00/min Rotor." in page.js("document.body.innerText")


def test_demand_targets_are_circles_fed_by_their_node(page):
    """A demand target is its own purple circle; the node making it keeps a production border."""
    page.open(page.base_url, plan(items=["Smart Plating", "Reinforced Iron Plate"], rates=[2, 3],
                                  merges={RIP_SP: "Reinforced Iron Plate"}))
    demand = "demand|Reinforced Iron Plate"
    assert page.js(label(demand)) == "Reinforced Iron Plate\n3.00/m\n(demand)"
    assert page.js(node_style(demand, "shape")) == "ellipse"
    assert page.js(node_style(demand, "border-color")) == "rgb(168,85,247)"
    assert page.js(node_style("Reinforced Iron Plate", "border-color")) == "rgb(245,158,11)"
    feeding = f"{EDGES}.filter(e => end(e.target()) === {json.dumps(demand)}).map(e => [end(e.source()), e.data('label')])"
    [[source, text]] = page.js(feeding)
    assert source == "Reinforced Iron Plate" and text.startswith("3.00/m")
    assert page.js(label("demand|Smart Plating")) == "Smart Plating\n2.00/m\n(demand)"

    # Clicking it shows the node that makes it; it can't be merged into
    page.js(f"void document.getElementById('cy')._cyreg.cy.getElementById({json.dumps(demand)}).emit('tap')")
    page.wait_until("document.getElementById('detail-id').textContent === 'Reinforced Iron Plate'")
    page.drag(page.node_position(demand), page.node_position("Reinforced Iron Plate"))
    page.wait(0.5)
    assert page.saved_plan()["merges"] == {RIP_SP: "Reinforced Iron Plate"}


def test_text_is_dark_on_bright_node_colors(page):
    page.open(page.base_url, plan(items=["Plastic"], rates=[20]))
    assert page.js(node_style("Plastic", "color")) == "rgb(15,23,42)"  # on #93c5fd
    assert page.js(node_style("Plastic__Crude Oil", "color")) == "rgb(248,250,252)"  # on the default slate


def test_inbound_production(page):
    page.open(page.base_url, plan(inbound=[{"item": "Reinforced Iron Plate", "rate": 3}]))
    inbound = "inbound:Reinforced Iron Plate"
    assert page.js(label(inbound)) == "Reinforced Iron Plate\n3.00 of 3.00/m\n(inbound)"
    assert RIP_SP not in page.node_ids()
    assert page.js(node_style(inbound, "border-color")) == "rgb(56,189,248)"
    page.select_node(inbound)
    for section in ("details-recipe-collapsible", "clock-controls"):
        assert page.js(f"document.getElementById('{section}').style.display") == "none"

    # Edited in the side panel and applied with Calculate, like the demands
    page.js("""(() => {
        document.querySelector('#inbound-rows input[name=rates]').value = '1';
        document.querySelector('#demand-form button[type=submit]').click();
    })()""")
    page.wait_until(f"{SAVED}.inbound[0].rate === 1")
    assert RIP_SP in page.node_ids()
    assert page.js(label(inbound)).startswith("Reinforced Iron Plate\n1.00 of 1.00/m")
    assert "#22c55e" not in page.js(badges(inbound))

    # More than the plan uses: a green dot, and the unused rate in the side panel
    page.js("""(() => {
        document.querySelector('#inbound-rows input[name=rates]').value = '10';
        document.querySelector('#demand-form button[type=submit]').click();
    })()""")
    page.wait_until(f"{SAVED}.inbound[0].rate === 10")
    assert page.js(label(inbound)).startswith("Reinforced Iron Plate\n5.00 of 10.00/m")
    assert "#22c55e" in page.js(badges(inbound))
    page.select_node(inbound)
    assert page.js("document.getElementById('detail-surplus-value').textContent") == "+5.00/min unused"


def edge_classes(source, target):
    return f"{EDGES}.filter(e => end(e.source()) === {json.dumps(source)} && end(e.target()) === {json.dumps(target)}).classes()"


def test_byproducts_go_to_the_sink(page):
    page.open(page.base_url, plan(items=["Aluminum Ingot"], rates=[60]))
    assert page.js(label("sink")) == "Sink\n220.00/m\n(1× AWESOME Sink)\nfluids can't be sunk!"
    assert page.js(node_style("sink", "shape")) == "ellipse"
    assert page.js(node_style("sink", "border-color")) == "rgb(239,68,68)"  # Water can't be sunk
    assert page.js(edge_classes("Aluminum Ingot__Aluminum Scrap", "sink")) == ["byproduct", "invalid"]
    assert page.js(edge_classes("Aluminum Ingot__Aluminum Scrap__Alumina Solution", "sink")) == ["byproduct"]

    page.select_node("sink")
    assert page.js("document.getElementById('detail-surplus-value').textContent") == "Fluids can't be sunk: Water"
    assert page.js("document.getElementById('detail-power').textContent") == "-30.00 MW"
    for section in ("details-recipe-collapsible", "clock-controls"):
        assert page.js(f"document.getElementById('{section}').style.display") == "none"


ALU_SCRAP = "Aluminum Ingot__Aluminum Scrap"
ALU_ALUMINA = f"{ALU_SCRAP}__Alumina Solution"


def test_calculate_uses_byproducts_and_an_edge_sends_them_to_the_sink(page):
    page.open(page.base_url, plan(items=["Aluminum Ingot"], rates=[60]))
    assert page.saved_plan().get("byproducts", {}) == {}  # loading a plan doesn't use them

    page.js("document.querySelector('#demand-form button[type=submit]').click()")
    page.wait_until(f"({SAVED}.byproducts || {{}})[{json.dumps(ALU_ALUMINA)}] === 'use'")
    assert page.js(edge_classes(ALU_ALUMINA, "Aluminum Ingot")) == ["byproduct", "used"]
    assert page.js(edge_classes(ALU_ALUMINA, "sink")) == ["byproduct"]  # 25 left over

    page.js(f"void {EDGES}.filter(e => end(e.source()) === {json.dumps(ALU_ALUMINA)} && end(e.target()) === 'Aluminum Ingot').emit('tap')")
    assert page.js("document.getElementById('byproduct-details').style.display") == "block"
    assert page.js("document.getElementById('node-details').style.display") == "none"
    assert page.js("document.getElementById('byproduct-used').textContent") == "75.00/min"
    assert page.js("document.getElementById('byproduct-toggle-btn').textContent") == "Send to Sink"

    page.js("document.getElementById('byproduct-toggle-btn').click()")
    page.wait_until(f"{SAVED}.byproducts[{json.dumps(ALU_ALUMINA)}] === 'sink'")
    cy_edges = f"{EDGES}.filter(e => end(e.source()) === {json.dumps(ALU_ALUMINA)} && end(e.target()) === 'Aluminum Ingot')"
    assert page.js(f"{cy_edges}.length") == 0  # no by-product edge any more
    assert "Aluminum Ingot__Silica" in page.node_ids()
    assert page.js("document.getElementById('byproduct-sunk').textContent") == "100.00/min"
    assert page.js("document.getElementById('byproduct-toggle-btn').textContent") == "Use as Supply"


def test_solving_a_byproduct_loop(page):
    scrap = "Water__Aluminum Casing__Aluminum Ingot__Aluminum Scrap"
    page.open(page.base_url, plan(items=["Water"], rates=[100], recipes={"Water": "Battery"}, byproducts={scrap: "use"}))
    assert page.js(edge_classes(scrap, "sink")) == ["byproduct", "invalid", "loop"]

    page.js(f"void {EDGES}.filter(e => end(e.source()) === {json.dumps(scrap)} && end(e.target()) === 'sink').emit('tap')")
    assert page.js("document.getElementById('byproduct-solve-btn').textContent") == "Solve Loop"
    page.js("document.getElementById('byproduct-solve-btn').click()")
    page.wait_until(f"{SAVED}.byproducts[{json.dumps(scrap)}] === 'solve'")
    assert page.js(edge_classes(scrap, "Water")) == ["byproduct", "used", "loop"]
    assert "(loop, solved)" in page.js(f"{EDGES}.filter(e => end(e.source()) === {json.dumps(scrap)} && end(e.target()) === 'Water').data('label')")
    assert page.js("document.getElementById('byproduct-hint').textContent").startswith("Loop solved")
    assert page.js("document.getElementById('byproduct-solve-btn').textContent") == "Stop Solving"


def test_legend_toggles_and_is_remembered(page):
    page.open(page.base_url, plan())
    assert page.js("document.getElementById('legend').hidden")
    page.js("document.getElementById('legend-toggle').click()")
    assert not page.js("document.getElementById('legend').hidden")
    assert "Demand target" in page.js("document.getElementById('legend').textContent")
    assert "Logistics node" in page.js("document.getElementById('legend').textContent")

    page.send("Page.reload")
    page.wait(0.3)
    page.wait_until("document.readyState === 'complete' && document.querySelectorAll('.color-input').length > 0")
    assert not page.js("document.getElementById('legend').hidden")
    page.js("document.getElementById('legend-toggle').click()")
    assert page.js("document.getElementById('legend').hidden")


def badges(node_id):
    """The node's badge image (status dot, built mark) as SVG text."""
    cy = "document.getElementById('cy')._cyreg.cy"
    return f"atob(({cy}.getElementById({json.dumps(node_id)}).data('backgroundImage') || ',').split(',')[1])"


def test_marking_buildings_built(page):
    page.open(page.base_url, {"items": ["Smart Plating"], "rates": [20], "clocks": {}, "merges": {}, "recipes": {}})
    node = "document.getElementById('cy')._cyreg.cy.getElementById('Smart Plating')"
    page.select_node("Smart Plating")
    assert page.js("document.getElementById('built-of').textContent") == "of 10"

    # Some built: "4/10" on the node, which stays bright
    page.js("""(() => {
        const input = document.getElementById('built-count');
        input.value = '4';
        input.dispatchEvent(new Event('change'));
    })()""")
    assert page.saved_plan()["built"] == {"Smart Plating": {"count": 4, "recipe": "Smart Plating"}}
    assert "4/10" in page.js(badges("Smart Plating"))
    assert not page.js(f"{node}.hasClass('done')")
    assert page.js("document.getElementById('built-hint').textContent") == "6 left to build."

    # All built: faded, with a check
    page.js("document.getElementById('built-all-btn').click()")
    assert page.saved_plan()["built"]["Smart Plating"]["count"] == 10
    assert page.js(f"{node}.hasClass('done')")
    assert "/10" not in page.js(badges("Smart Plating"))
    assert page.js("document.getElementById('built-all-btn').textContent") == "Not Built"

    # The plan grows: no longer done, "10/15"
    rows = "document.querySelectorAll('#demand-rows input[name=rates]')"
    page.js(f"{rows}[0].value = '30'; document.getElementById('demand-form').requestSubmit()")
    page.wait_until(f"{badges('Smart Plating')}.includes('10/15')")
    assert not page.js(f"{node}.hasClass('done')")

    # Built for another recipe: doesn't count, and the panel says so
    switch_recipe(page, "Smart Plating", "Alternate: Plastic Smart Plating")
    assert not page.js(f"{node}.hasClass('done')")
    assert page.js("document.getElementById('built-hint').textContent").startswith("10 were marked built for Smart Plating")

    # Undo goes back to the recipe they were built for
    page.js("document.getElementById('undo-btn').click()")
    page.wait_until(f"{badges('Smart Plating')}.includes('10/15')")

    # Clear Built Marks
    page.js("window.confirm = () => true; document.getElementById('clear-built-btn').click()")
    assert page.saved_plan()["built"] == {}
    assert "/15" not in page.js(badges("Smart Plating"))


def test_new_plan_clears_everything_and_undo_brings_it_back(page):
    page.open(page.base_url, plan(recipes={RIP_SP: "Alternate: Bolted Iron Plate"}, inbound=[{"item": "Screws", "rate": 10}],
                                  built={"Smart Plating": {"count": 1, "recipe": "Smart Plating"}}))
    page.select_node("Smart Plating")
    page.js("window.confirm = () => true; document.getElementById('new-plan-btn').click()")
    saved = page.saved_plan()
    assert (saved["items"], saved["inbound"], saved["recipes"], saved["built"]) == ([], [], {}, {})
    assert page.node_ids() == []
    assert page.js("document.getElementById('node-details').style.display") == "none"
    assert page.js("document.querySelectorAll('#demand-rows .demand-row').length") == 1

    page.js("document.getElementById('undo-btn').click()")
    page.wait_until("document.getElementById('cy')._cyreg.cy.nodes().length > 0")
    assert page.saved_plan()["recipes"] == {RIP_SP: "Alternate: Bolted Iron Plate"}
    assert page.saved_plan()["items"] == ["Smart Plating", "Modular Frame"]

    page.js("document.getElementById('redo-btn').click()")
    page.wait_until("document.getElementById('cy')._cyreg.cy.nodes().length === 0")


def test_selecting_opens_the_node_tab(page):
    page.open(page.base_url, plan())
    active = "document.querySelector('.tab-content.active').id"
    assert page.js(active) == "planner-tab"
    page.js("document.querySelector('.tab[data-tab=node]').click()")
    assert not page.js("document.getElementById('node-empty').hidden")  # nothing selected yet

    page.js("document.querySelector('.tab[data-tab=planner]').click()")
    page.select_node("Smart Plating")
    assert page.js(active) == "node-tab"
    assert page.js("document.getElementById('node-empty').hidden")
    assert page.js("document.querySelector('.tab.active').dataset.tab") == "node"
    # The plan-wide controls stay on the Planner tab
    assert page.js("document.getElementById('demand-form').closest('.tab-content').id") == "planner-tab"


def test_clearing_clocks_removes_the_dashed_border(page):
    page.open(page.base_url, plan())
    node = "document.getElementById('cy')._cyreg.cy.getElementById('Smart Plating')"
    page.select_node("Smart Plating")
    page.js("document.getElementById('clock-all').value = '150'; document.getElementById('apply-clocks-btn').click()")
    page.wait_until(f"{node}.hasClass('clocked')")
    page.js("document.getElementById('clear-clocks-node-btn').click()")
    page.wait_until(f"!{node}.hasClass('clocked')")


def test_guide_panel(page):
    page.open(page.base_url, plan())
    guide = "document.getElementById('guide')"
    legend = "document.getElementById('legend')"
    page.js("document.getElementById('guide-toggle').click()")
    page.wait_until("Boolean(document.querySelector('#guide-content h2#clock-speeds'))")
    assert not page.js(f"{guide}.hidden")
    page.wait_until("[...document.querySelectorAll('#guide-content img')].some(i => i.complete && i.naturalWidth > 0)")

    # The legend and the guide close each other
    page.js("document.getElementById('legend-toggle').click()")
    assert page.js(f"{guide}.hidden") and not page.js(f"{legend}.hidden")
    page.js("document.getElementById('guide-toggle').click()")
    assert page.js(f"{legend}.hidden") and not page.js(f"{guide}.hidden")
    page.js("document.getElementById('guide-close').click()")
    assert page.js(f"{guide}.hidden")

    # "?" opens it at its section; the contents scroll it too
    page.select_node(RIP_SP)
    page.js("document.querySelector('.help-link[data-guide=clock-speeds]').click()")
    at_top = lambda section: (f"(() => {{ const c = document.getElementById('guide-content'); "
                              f"return Math.abs(c.querySelector('#{section}').offsetTop - c.scrollTop) < 5; }})()")
    page.wait_until(at_top("clock-speeds"))
    assert page.js("document.getElementById('detail-id').textContent") == RIP_SP  # the panel is as it was
    page.js("document.querySelector('.guide-toc a[href=\"#the-chain-tab\"]').click()")
    page.wait_until(at_top("the-chain-tab"))


def test_recipe_list_is_the_selected_nodes_when_responses_cross(page):
    """A slow recipe list for the node selected before doesn't replace the selected node's."""
    page.open(page.base_url, plan())
    page.js("""(() => {
        const original = window.fetch;
        window.fetch = (url, ...rest) => String(url).includes('item_name=Smart%20Plating')
            ? new Promise(resolve => setTimeout(() => resolve(original(url, ...rest)), 600))
            : original(url, ...rest);
        return true;
    })()""")
    page.select_node("Smart Plating")
    page.select_node(RIP_SP)
    page.wait(1.2)
    options = page.js("[...document.getElementById('recipe-select').options].map(o => o.value)")
    assert "Alternate: Bolted Iron Plate" in options
    assert "Alternate: Plastic Smart Plating" not in options
