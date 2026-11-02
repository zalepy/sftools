"""Browser tests of the book's name, New Book and unsaved changes (ticket 060)."""
import json

BOOK = "JSON.parse(localStorage.getItem('sf_logistics_book'))"
ROTORS = {"mode": "logistics", "items": ["Rotor"], "rates": [4]}
PLATES = {"mode": "logistics", "items": ["Reinforced Iron Plate"], "rates": [5]}


def book_name(page):
    return page.js("document.getElementById('book-name').textContent")


def rename_book(page, name):
    page.js("document.getElementById('book-name').dispatchEvent(new MouseEvent('dblclick', {bubbles: true}))")
    page.js(f"""(() => {{
        const input = document.querySelector('#plan-tabs > .plan-tab-input');
        input.value = {json.dumps(name)};
        input.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter'}}));
    }})()""")


def count_dialogs(page, answer=True):
    """Answers confirm() with `answer` and counts how often it's asked."""
    page.js(f"window.__asked = []; window.confirm = q => {{ window.__asked.push(q); return {json.dumps(answer)}; }}")


def test_the_book_is_named_and_saved_under_its_name(page):
    page.open(page.base_url, ROTORS)
    assert book_name(page) == "Book"  # a book from before 060: no name, and nothing changed yet

    rename_book(page, "Main")
    assert book_name(page) == "Main •"  # renaming is a change
    assert page.js(f"{BOOK}.name") == "Main"

    page.capture_downloads()
    page.js("document.getElementById('save-book-btn').click()")
    assert page.js("window.__files") == ["sf_planner_Main.json"]
    book = json.loads(page.js("window.__blob.text()"))
    assert book["name"] == "Main" and "changed" not in book
    assert book_name(page) == "Main"  # saved: the mark goes

    # The mark comes with a change and stays over a reload
    page.calculate("Reinforced Iron Plate", 5)
    assert book_name(page) == "Main •"
    page.send("Page.reload")
    page.wait_until("document.readyState === 'complete' && !document.getElementById('calculate-btn').disabled")
    page.wait_until(page.has_node("Reinforced Iron Plate"))
    assert book_name(page) == "Main •"


def test_showing_tabs_is_not_a_change(page):
    """Opening a tab or the page calculates and keeps the plan again, but changes nothing in the book."""
    page.open(page.base_url, ROTORS)
    page.js("document.getElementById('add-tab-btn').click()")
    page.calculate("Reinforced Iron Plate", 5)
    page.capture_downloads()
    page.js("document.getElementById('save-book-btn').click()")
    assert book_name(page) == "Book"

    page.click_tab("Plan 1")
    page.wait_until(page.has_node("Rotor"))
    page.click_tab("Plan 2")
    page.wait_until(page.has_node("Reinforced Iron Plate"))
    page.send("Page.reload")
    page.wait_until("document.readyState === 'complete' && !document.getElementById('calculate-btn').disabled")
    page.wait_until(page.has_node("Reinforced Iron Plate"))
    assert book_name(page) == "Book"

    # Renaming a tab, adding one, closing one: changes
    page.js("document.getElementById('add-tab-btn').click()")
    assert book_name(page) == "Book •"


def test_loading_a_book_asks_only_with_unsaved_changes(page):
    page.open(page.base_url, ROTORS)
    rad = {"mode": "logistics", "name": "RAD", "tabs": [
        {"id": "u", "name": "Uranium", "plan": ROTORS}, {"id": "p", "name": "Plutonium", "plan": PLATES}], "active": "p"}

    # Nothing changed since the page loaded the saved book: it loads without asking, under its name
    count_dialogs(page)
    page.import_file(rad)
    page.wait_until("document.querySelectorAll('.plan-tab').length === 2")
    assert page.js("window.__asked") == []
    assert book_name(page) == "RAD" and page.tab_names() == ["Uranium", "Plutonium"] and page.active_name() == "Plutonium"
    page.wait_until(page.has_node("Reinforced Iron Plate"))
    assert book_name(page) == "RAD"  # its tab shown: still as loaded

    # With a change, it asks, naming both books; No keeps this one
    page.calculate("Modular Frame", 1)
    count_dialogs(page, answer=False)
    main = {"mode": "logistics", "name": "Main", "tabs": [{"id": "m", "name": "Frames", "plan": ROTORS}]}
    page.import_file(main)
    assert page.js("window.__asked") == ['"RAD" has unsaved changes. Load "Main" (1 tab) in place of its 2 tabs?']
    assert book_name(page) == "RAD •" and page.tab_names() == ["Uranium", "Plutonium"]

    # Yes loads it
    count_dialogs(page)
    page.import_file(main)
    page.wait_until("document.querySelectorAll('.plan-tab').length === 1")
    assert book_name(page) == "Main" and page.tab_names() == ["Frames"]

    # A book file without a name (saved before 060) takes the file's
    page.import_file({**main, "name": None}, "sf_planner_book.json")
    page.wait_until("document.getElementById('book-name').textContent === 'book'")


def test_new_book(page):
    page.open(page.base_url, ROTORS)
    page.js("localStorage.setItem('sf_planner_recipes', JSON.stringify({'Screws': 'Alternate: Cast Screws'}))")
    page.js("document.getElementById('add-tab-btn').click()")  # a change
    count_dialogs(page, answer=False)
    page.js("window.prompt = () => 'RAD'; document.getElementById('new-book-btn').click()")
    assert page.js("window.__asked") == ['"Book" has unsaved changes. Start "RAD" in place of its 2 tabs?']
    assert page.tab_names() == ["Plan 1", "Plan 2"]

    count_dialogs(page)
    page.js("document.getElementById('new-book-btn').click()")
    page.wait_until("document.querySelectorAll('.plan-tab').length === 1")
    page.wait_until("document.getElementById('cy')._cyreg.cy.nodes().length === 0")
    assert page.tab_names() == ["Plan 1"] and book_name(page) == "RAD"
    assert page.js(f"{BOOK}.chain.links") == []
    assert page.js("JSON.parse(localStorage.getItem('sf_planner_recipes'))") == {"Screws": "Alternate: Cast Screws"}

    # Cancelling the name leaves the book as it is
    page.js("window.prompt = () => null; document.getElementById('new-book-btn').click()")
    assert book_name(page) == "RAD"
