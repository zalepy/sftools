"""Browser tests of plan tabs and Save Book (ticket 039)."""
import json
import os
import tempfile

ROTORS = {"items": ["Rotor"], "rates": [4], "merges": {}, "recipes": {}, "clocks": {}}
PLATES = {"items": ["Reinforced Iron Plate"], "rates": [5], "merges": {}, "recipes": {}, "clocks": {}}
BOOK = "JSON.parse(localStorage.getItem('sf_planner_book'))"


def tab_names(page):
    return page.js("[...document.querySelectorAll('.plan-tab .plan-tab-name')].map(e => e.textContent)")


def active_name(page):
    return page.js("document.querySelector('.plan-tab.active .plan-tab-name').textContent")


def click_tab(page, name):
    page.js(f"""[...document.querySelectorAll('.plan-tab')]
        .find(t => t.querySelector('.plan-tab-name').textContent === {json.dumps(name)}).click()""")
    page.wait_until(f"document.querySelector('.plan-tab.active .plan-tab-name').textContent === {json.dumps(name)}")


def has_node(page, node_id):
    return f"document.getElementById('cy')._cyreg.cy.getElementById({json.dumps(node_id)}).length === 1"


def calculate(page, item, rate):
    page.js(f"""(() => {{
        const row = document.querySelector('#demand-rows .demand-row');
        row.querySelector('[name=items]').value = {json.dumps(item)};
        row.querySelector('[name=rates]').value = {json.dumps(str(rate))};
        document.querySelector('#demand-form button[type=submit]').click();
    }})()""")
    page.wait_until(has_node(page, item))


def import_file(page, content):
    """Picks a file in the Import button's file input, as the user would."""
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(content, f)
    try:
        root = page.send("DOM.getDocument")["root"]["nodeId"]
        node = page.send("DOM.querySelector", nodeId=root, selector="#import-input")["nodeId"]
        page.send("DOM.setFileInputFiles", files=[path], nodeId=node)
        page.wait(0.5)
    finally:
        os.remove(path)


def capture_downloads(page):
    page.js("""(() => {
        window.__files = [];
        const create = URL.createObjectURL;
        URL.createObjectURL = blob => { window.__blob = blob; return create(blob); };
        HTMLAnchorElement.prototype.click = function () { window.__files.push(this.download); };
    })()""")


def test_tabs_keep_their_own_plans_and_undo(page):
    # A plan saved before tabs becomes the first tab
    page.open(page.base_url, ROTORS)
    assert tab_names(page) == ["Plan 1"]
    page.wait_until(f"{BOOK} !== null")
    assert page.js(f"{BOOK}.tabs[0].plan.items") == ["Rotor"]

    # A new tab is empty, and has its own plan and undo
    page.js("document.getElementById('add-tab-btn').click()")
    page.wait_until("document.getElementById('cy')._cyreg.cy.nodes().length === 0")
    assert tab_names(page) == ["Plan 1", "Plan 2"] and active_name(page) == "Plan 2"
    assert page.js("document.getElementById('undo-btn').disabled")
    calculate(page, "Reinforced Iron Plate", 5)
    assert page.saved_plan()["items"] == ["Reinforced Iron Plate"]  # the active tab's plan, as before tabs

    # Back to the first: its plan, its undo
    click_tab(page, "Plan 1")
    page.wait_until(has_node(page, "Rotor"))
    assert not page.js(has_node(page, "Reinforced Iron Plate"))
    assert page.js(f"{BOOK}.tabs.map(t => t.plan.items)") == [["Rotor"], ["Reinforced Iron Plate"]]

    # Rename by double-click
    page.js("document.querySelector('.plan-tab.active .plan-tab-name').dispatchEvent(new MouseEvent('dblclick', {bubbles: true}))")
    page.js("""(() => {
        const input = document.querySelector('.plan-tab-input');
        input.value = 'Rotors';
        input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
    })()""")
    assert tab_names(page) == ["Rotors", "Plan 2"]

    # Duplicate: the same plan in a new tab next to it
    page.js("document.getElementById('duplicate-tab-btn').click()")
    page.wait_until("document.querySelector('.plan-tab.active .plan-tab-name').textContent === 'Rotors (copy)'")
    page.wait_until(has_node(page, "Rotor"))
    assert tab_names(page) == ["Rotors", "Rotors (copy)", "Plan 2"]

    # Kept across a reload, with the active tab
    page.send("Page.reload")
    page.wait_until("document.readyState === 'complete' && document.querySelectorAll('.plan-tab').length === 3")
    page.wait_until(has_node(page, "Rotor"))
    assert active_name(page) == "Rotors (copy)"

    # Close: asks first when the tab has a plan, and shows a neighbour
    page.js("window.confirm = () => true; document.querySelector('.plan-tab.active .plan-tab-close').click()")
    page.wait_until("document.querySelectorAll('.plan-tab').length === 2")
    assert tab_names(page) == ["Rotors", "Plan 2"]
    page.wait_until(has_node(page, "Reinforced Iron Plate"))
    assert active_name(page) == "Plan 2"


def test_save_book_and_import(page):
    page.open(page.base_url, ROTORS)
    page.js("document.getElementById('add-tab-btn').click()")
    calculate(page, "Reinforced Iron Plate", 5)
    capture_downloads(page)

    # Save Book: every tab in one file
    page.js("document.getElementById('save-book-btn').click()")
    book = json.loads(page.js("window.__blob.text()"))
    assert page.js("window.__files") == ["sf_planner_book.json"]
    assert [t["name"] for t in book["tabs"]] == ["Plan 1", "Plan 2"]
    assert [t["plan"]["items"] for t in book["tabs"]] == [["Rotor"], ["Reinforced Iron Plate"]]

    # Export Plan: the active tab, named after it
    page.js("document.getElementById('export-btn').click()")
    plan = json.loads(page.js("window.__blob.text()"))
    assert page.js("window.__files[1]") == "sf_planner_Plan_2.json"
    assert plan["items"] == ["Reinforced Iron Plate"] and plan["name"] == "Plan 2"

    # Importing a plan opens it in a new tab
    import_file(page, {**PLATES, "items": ["Modular Frame"], "rates": [1], "name": "Frames"})
    page.wait_until(has_node(page, "Modular Frame"))
    assert tab_names(page) == ["Plan 1", "Plan 2", "Frames"]

    # Importing a book replaces all the tabs (after asking)
    page.js("window.confirm = () => true")
    import_file(page, book)
    page.wait_until("document.querySelectorAll('.plan-tab').length === 2")
    assert tab_names(page) == ["Plan 1", "Plan 2"]
    page.wait_until(has_node(page, "Reinforced Iron Plate"))


def test_a_logistics_book_is_refused_in_simple_mode(page):
    page.open(page.base_url, ROTORS)
    import_file(page, {"mode": "logistics", "tabs": [{"id": "t1", "name": "L", "plan": {"mode": "logistics", **ROTORS}}]})
    assert page.dialogs and page.dialogs[-1].startswith("This is a logistics mode plan")
    assert tab_names(page) == ["Plan 1"]


# --- The chain tab (ticket 040) ---

CCY = "document.getElementById('ccy')._cyreg.cy"


def tab_plan(items=(), rates=(), inbound=()):
    return {"mode": "simple", "items": list(items), "rates": list(rates), "inbound": list(inbound),
            "merges": {}, "recipes": {}, "clocks": {}}


# AW makes 13 Motors; ACU takes 6 and MFG 7 as inbound; XYZ makes 5 more
CHAIN_BOOK = {"active": "aw", "tabs": [
    {"id": "aw", "name": "AW", "plan": tab_plan(["Motor"], [13])},
    {"id": "acu", "name": "ACU", "plan": tab_plan(inbound=[{"item": "Motor", "rate": 6}])},
    {"id": "mfg", "name": "MFG", "plan": tab_plan(inbound=[{"item": "Motor", "rate": 7}])},
    {"id": "xyz", "name": "XYZ", "plan": tab_plan(["Motor"], [5])},
]}


def open_book(page, book):
    page.open(page.base_url)
    page.js(f"localStorage.setItem('sf_planner_book', JSON.stringify({json.dumps(book)}))")
    page.send("Page.reload")
    page.wait(0.3)
    page.wait_until(f"document.querySelectorAll('.plan-tab').length === {len(book['tabs'])}")


def ccy_position(page, node_id):
    return page.js(f"""(() => {{
        const container = document.getElementById('ccy');
        const box = container.getBoundingClientRect();
        const p = container._cyreg.cy.getElementById({json.dumps(node_id)}).renderedPosition();
        return [box.left + p.x, box.top + p.y];
    }})()""")


def link(page, supply, need):
    page.drag(ccy_position(page, supply), ccy_position(page, need))
    page.wait(0.2)


def label_of(page, element_id):
    return page.js(f"{CCY}.getElementById({json.dumps(element_id)}).data('label')")


def classes(page, node_id):
    return page.js(f"{CCY}.getElementById({json.dumps(node_id)}).classes()")


def links(page):
    return page.js(f"{BOOK}.chain.links.map(l => l.from.tab + '>' + l.to.tab + ':' + l.to.item)")


def test_the_chain_tab_links_plans(page):
    open_book(page, CHAIN_BOOK)
    page.js("document.getElementById('chain-tab-btn').click()")
    page.wait_until("!document.getElementById('chain-view').hidden")
    assert page.js("document.querySelector('.plan-tab.behind .plan-tab-name').textContent") == "AW"
    # Each tab a box: demand targets supply, inbound production needs; unlinked nodes are neutral
    assert sorted(page.js(f"{CCY}.nodes('.supply, .need').map(n => n.id())")) == \
        ["n|acu|Motor", "n|mfg|Motor", "s|aw|Motor", "s|xyz|Motor"]
    assert classes(page, "s|aw|Motor") == ["supply"]

    # One supply, two needs: each link carries what its need asks for
    link(page, "s|aw|Motor", "n|acu|Motor")
    assert links(page) == ["aw>acu:Motor"]
    assert label_of(page, "l|aw|acu|Motor") == "6.00/m"
    assert "surplus" in classes(page, "s|aw|Motor") and label_of(page, "s|aw|Motor").endswith("7.00/m spare")
    assert "ok" in classes(page, "n|acu|Motor")
    link(page, "s|aw|Motor", "n|mfg|Motor")
    assert label_of(page, "l|aw|mfg|Motor") == "7.00/m"
    assert "ok" in classes(page, "s|aw|Motor") and "ok" in classes(page, "n|mfg|Motor")

    # Several supplies into a need that has one already, while AW feeds two: refused
    link(page, "s|xyz|Motor", "n|mfg|Motor")
    page.wait_until("document.getElementById('toast').textContent === "
                    "'Motor: one plan can feed several, or several can feed one, not both.'")
    assert len(links(page)) == 2

    # A plan changed: the highlights follow, the other plans stay as they are
    page.js(f"void {CCY}.getElementById('box|aw').emit('dbltap')")
    page.wait_until("document.getElementById('chain-view').hidden")
    page.js("""(() => {
        document.querySelector('#demand-rows [name=rates]').value = '10';
        document.querySelector('#demand-form button[type=submit]').click();
    })()""")
    page.wait_until(f"{BOOK}.tabs[0].plan.rates[0] === 10")
    page.js("document.getElementById('chain-tab-btn').click()")
    page.wait_until("!document.getElementById('chain-view').hidden")
    assert "short" in classes(page, "s|aw|Motor") and label_of(page, "s|aw|Motor").endswith("3.00/m short")
    assert page.js(f"{BOOK}.tabs[1].plan.inbound") == [{"item": "Motor", "rate": 6}]

    # Delete a link
    page.js(f"void {CCY}.getElementById('l|aw|mfg|Motor').select()")
    page.js("document.getElementById('chain-delete').click()")
    assert links(page) == ["aw>acu:Motor"]

    # Saved with the book; closing a tab drops its links
    capture_downloads(page)
    page.js("document.getElementById('save-book-btn').click()")
    saved_book = json.loads(page.js("window.__blob.text()"))
    assert [l["to"]["tab"] for l in saved_book["chain"]["links"]] == ["acu"]
    page.js("window.confirm = () => true; document.querySelector('.plan-tab[data-id=acu] .plan-tab-close').click()")
    page.wait_until(f"{BOOK}.chain.links.length === 0")
    assert not page.js("document.getElementById('chain-view').hidden")  # still shown


def test_many_supplies_into_one_need(page):
    open_book(page, {**CHAIN_BOOK, "tabs": CHAIN_BOOK["tabs"][:3]
                     + [{"id": "xyz", "name": "XYZ", "plan": tab_plan(["Motor"], [3])}]})
    page.js("document.getElementById('chain-tab-btn').click()")
    page.wait_until("!document.getElementById('chain-view').hidden")
    link(page, "s|aw|Motor", "n|mfg|Motor")
    link(page, "s|xyz|Motor", "n|mfg|Motor")
    # Each link carries what its supply makes: 13 + 3 for a need of 7
    assert label_of(page, "l|aw|mfg|Motor") == "13.00/m" and label_of(page, "l|xyz|mfg|Motor") == "3.00/m"
    assert "surplus" in classes(page, "n|mfg|Motor") and label_of(page, "n|mfg|Motor").endswith("9.00/m more")
    # A link joins the same item only
    assert page.js(f"{CCY}.getElementById('n|acu|Motor').length") == 1
