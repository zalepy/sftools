"""Browser tests of the notes per node and per plan (ticket 046; see conftest.py for the fixtures)."""
import json

TWO_ROOTS = {"items": ["Smart Plating", "Modular Frame"], "rates": [2, 2],
             "clocks": {}, "merges": {}, "recipes": {}}


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

NOTE_BOX = "document.getElementById('note-box')"


def type_node_note(page, text):
    page.js(f"document.getElementById('node-note').value = {json.dumps(text)}")


def save_node_note(page, text):
    type_node_note(page, text)
    page.js("document.getElementById('save-node-note-btn').click()")


def test_node_and_plan_notes_are_saved_with_the_plan(page):
    page.open(page.base_url, TWO_ROOTS)
    page.select_node("Smart Plating")
    assert page.js("document.getElementById('node-note').value") == ""
    save_node_note(page, "Built at the river\nneeds power")
    assert page.saved_plan()["notes"] == {"Smart Plating": "Built at the river\nneeds power"}

    page.js("document.getElementById('plan-note').value = 'Main base'; document.getElementById('save-plan-note-btn').click()")
    assert page.saved_plan()["planNote"] == "Main base"

    # Another node has its own (empty) note; back on the first, its note is there
    page.select_node("Modular Frame")
    assert page.js("document.getElementById('node-note').value") == ""
    page.select_node("Smart Plating")
    assert page.js("document.getElementById('node-note').value") == "Built at the river\nneeds power"

    # An empty note is removed; undo brings it back
    save_node_note(page, "  ")
    assert page.saved_plan()["notes"] == {}
    page.js("document.getElementById('undo-btn').click()")
    page.wait_until("JSON.parse(localStorage.getItem('sf_logistics_state')).notes['Smart Plating']")
    page.wait_until("document.getElementById('node-note').value.endsWith('needs power')")

    # Reloaded: the notes come back with the plan
    page.send("Page.reload")
    page.wait_until("document.readyState === 'complete' && document.getElementById('cy')._cyreg.cy.nodes().length > 0", timeout=30)
    page.wait_until("document.getElementById('plan-note').value === 'Main base'")
    page.select_node("Smart Plating")
    assert page.js("document.getElementById('node-note').value").endswith("needs power")


def test_a_recipe_change_is_added_to_the_note(page):
    page.open(page.base_url, {"items": ["Smart Plating"], "rates": [20], "clocks": {}, "merges": {}, "recipes": {}})
    page.select_node("Smart Plating")
    save_node_note(page, "Line 1")
    switch_recipe(page, "Smart Plating", "Alternate: Plastic Smart Plating")
    note = page.saved_plan()["notes"]["Smart Plating"]
    lines = note.split("\n")
    assert lines[0] == "Line 1"
    assert lines[1].endswith(": recipe changed from Smart Plating to Alternate: Plastic Smart Plating")
    assert len(lines[1].split(":")[0]) == len("dd.mm.yy")
    assert page.js("document.getElementById('node-note').value") == note

    # A node without a note gets none
    switch_recipe(page, "Smart Plating__Reinforced Iron Plate", "Alternate: Adhered Iron Plate")
    assert list(page.saved_plan()["notes"]) == ["Smart Plating"]


def test_unsaved_note_asks_before_it_goes(page):
    page.open(page.base_url, TWO_ROOTS)
    page.select_node("Smart Plating")
    type_node_note(page, "draft")

    # Kept: the node stays selected, with the draft
    page.js("window.confirm = () => false")
    page.js("import('/static/js/graph.js').then(g => g.reselectNode('Modular Frame'))")
    page.wait(0.3)
    assert page.js("document.getElementById('detail-id').textContent") == "Smart Plating"
    assert page.js("document.getElementById('node-note').value") == "draft"

    # Discarded: the other node is shown, and the draft is gone
    page.js("window.confirm = () => true")
    page.select_node("Modular Frame")
    page.select_node("Smart Plating")
    assert page.js("document.getElementById('node-note').value") == ""
    assert "notes" not in page.saved_plan() or page.saved_plan()["notes"] == {}


def test_a_note_goes_with_its_node_and_undo_brings_it_back(page):
    page.open(page.base_url, TWO_ROOTS)
    page.select_node("Modular Frame")
    save_node_note(page, "Frames here")

    # Modular Frame is no longer demanded: its node and its note go
    page.js("""(() => {
        document.querySelectorAll('#demand-rows .remove-row')[1].click();
        document.getElementById('demand-form').requestSubmit();
    })()""")
    page.wait_until("!document.getElementById('cy')._cyreg.cy.getElementById('Modular Frame').length")
    assert page.saved_plan()["notes"] == {}

    page.js("document.getElementById('undo-btn').click()")
    page.wait_until("document.getElementById('cy')._cyreg.cy.getElementById('Modular Frame').length > 0")
    assert page.saved_plan()["notes"] == {"Modular Frame": "Frames here"}


def test_the_note_box_shows_on_hover_and_while_selected(page):
    page.open(page.base_url, TWO_ROOTS)
    page.select_node("Modular Frame")
    save_node_note(page, "Frames here")
    # Selected: its note is shown where the legend is
    assert not page.js(f"{NOTE_BOX}.hidden")
    assert page.js("document.getElementById('note-box-text').textContent") == "Frames here"
    assert page.js("document.getElementById('note-box-title').textContent") == "Modular Frame"

    # Another node selected (no note): nothing shown
    page.select_node("Smart Plating")
    assert page.js(f"{NOTE_BOX}.hidden")

    # The mouse resting on the noted node shows its note; moving off hides it again
    x, y = page.node_position("Modular Frame")
    page.send("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    page.wait_until(f"!{NOTE_BOX}.hidden", timeout=3)
    assert page.js("document.getElementById('note-box-text').textContent") == "Frames here"
    page.send("Input.dispatchMouseEvent", type="mouseMoved", x=5, y=5)
    page.wait_until(f"{NOTE_BOX}.hidden", timeout=3)

    # Selected again, then a click on the empty graph deselects: hidden
    page.select_node("Modular Frame")
    assert not page.js(f"{NOTE_BOX}.hidden")
    page.js("document.getElementById('cy')._cyreg.cy.emit('tap'), true")
    assert page.js(f"{NOTE_BOX}.hidden")
