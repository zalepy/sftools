"""Browser tests of logistics mode (ticket 033): the /logistics page and its zoomed-in logistics nodes."""
import json

KEY = "sf_logistics_state"
BEAM = "Versatile Framework__Steel Beam"
BEAMS = {"mode": "logistics", "items": ["Versatile Framework", "Encased Industrial Beam"], "rates": [5, 12],
         "merges": {"Encased Industrial Beam__Steel Beam": BEAM}, "recipes": {}, "clocks": {}}
CY = "document.getElementById('cy')._cyreg.cy"
LCY = "document.getElementById('lcy')._cyreg.cy"


def open_logistics(page, plan=BEAMS):
    page.open(page.base_url + "logistics", plan, key=KEY)


def saved(page):
    return page.saved_plan(KEY)


def zoom_in(page, node_id=BEAM, side="out"):
    page.js(f"void {CY}.getElementById({json.dumps(f'{node_id}|{side}')}).emit('tap')")
    page.wait_until("document.getElementById('logistics-details').style.display === 'block'")
    page.js("document.getElementById('logistics-zoom-btn').click()")
    page.wait_until(f"!document.getElementById('logistics-view').hidden && {LCY}.nodes().length > 0")


def lcy_position(page, node_id):
    return page.js(f"""(() => {{
        const container = document.getElementById('lcy');
        const box = container.getBoundingClientRect();
        const p = container._cyreg.cy.getElementById({json.dumps(node_id)}).renderedPosition();
        return [box.left + p.x, box.top + p.y];
    }})()""")


def dot_position(page, node_id):
    """A free output dot of the node, where belts are dragged from."""
    return lcy_position(page, f"__dot|{node_id}|0")


def fit(page):
    """The whole side in view, so every node can be reached with the mouse."""
    page.js(f"void {LCY}.fit(undefined, 30)")


def test_logistics_page_is_its_own_mode(page):
    open_logistics(page)
    assert page.js("document.body.dataset.mode") == "logistics"
    assert page.js("document.querySelector('.mode-link').getAttribute('href')") == "/"
    assert page.js(f"{CY}.getElementById({json.dumps(BEAM + '|out')}).data('label')") == "2"  # two mergers
    assert page.js(f"{CY}.getElementById({json.dumps(BEAM + '|in')}).data('label')") == "5"  # a 5-way manifold
    # Belts run between logistics nodes, labelled with their tier
    edge = f"{CY}.edges().filter(e => e.source().id() === {json.dumps(BEAM + '|out')} && e.target().id() === 'Versatile Framework|in')"
    assert page.js(f"{edge}.data('label')") == "30.00/m · Mk.1"
    # No splits here; the plan is kept apart from the simple mode's
    page.select_node(BEAM)
    assert page.js("getComputedStyle(document.getElementById('split-controls')).display") == "none"
    assert saved(page)["mode"] == "logistics"
    assert page.saved_plan() is None
    message = page.js("import('/static/js/state.js').then(m => m.wrongMode({items: []}))")
    assert message.startswith("This is a simple mode plan")


def test_settings_change_the_belts(page):
    open_logistics(page)
    page.js("""(() => {
        const select = document.getElementById('belt-tier');
        select.value = '1';
        select.dispatchEvent(new Event('change'));
    })()""")
    page.wait_until(f"JSON.parse(localStorage.getItem({json.dumps(KEY)})).logistics.settings.belt_tier === 1")
    # 136.36/min of Steel Ingot needs three Mk.1 belts
    edge = f"{CY}.edges().filter(e => e.target().id() === {json.dumps(BEAM + '|in')} && e.data('label').includes('136.36'))"
    assert page.js(f"{edge}.data('label')") == "136.36/m · 3× Mk.1"
    assert page.js(f"{edge}.hasClass('multi')")


def click(page, position):
    x, y = position
    page.send("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    page.send("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
    page.send("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", clickCount=1)
    page.wait(0.2)


def belts_between(source, target):
    return f"{LCY}.edges().filter(e => e.source().id() === {json.dumps(source)} && e.target().id() === {json.dumps(target)}).length"


def test_editing_a_logistics_node(page):
    framework, encased = "x|Versatile Framework|Steel Beam", "x|Encased Industrial Beam|Steel Beam"
    open_logistics(page)
    zoom_in(page)
    assert page.js("document.getElementById('lv-title').textContent").startswith("Output logistics: Steel Beam")
    # Buildings on the left, exits on the right; the exits merge the buildings' belts themselves
    xs = page.js(f"{LCY}.nodes('.real').map(n => [n.data('raw').kind, n.position().x])")
    assert max(x for kind, x in xs if kind == "building") < min(x for kind, x in xs if kind == "exit")
    assert page.js(belts_between("b5|Steel Beam", encased)) == 1

    # Take Constructor 5 off the Encased Beam exit, onto a buffer: a belt from its output dot
    page.js(f"void {LCY}.edges().filter(e => e.source().id() === 'b5|Steel Beam').select()")
    page.js("document.getElementById('lv-delete').click()")
    page.wait_until(f"{LCY}.edges().filter(e => e.source().id() === 'b5|Steel Beam').length === 0")
    assert saved(page)["logistics"]["layouts"][f"{BEAM}|out"]["belts"]
    page.js("document.querySelector('.lv-add[data-kind=buffer]').click()")
    page.wait_until(f"{LCY}.nodes('.buffer').length === 1")
    buffer = page.js(f"{LCY}.nodes('.buffer')[0].id()")
    fit(page)
    page.drag(dot_position(page, "b5|Steel Beam"), lcy_position(page, buffer))
    page.wait_until(belts_between("b5|Steel Beam", buffer) + " === 1")
    assert page.js("document.getElementById('lv-warnings').textContent") == \
        "Exit to Encased Industrial Beam gets 30.00 of 36.00/min"  # Constructors 1 and 2 only
    assert page.js(f"{CY}.getElementById({json.dumps(BEAM + '|out')}).hasClass('warn')")

    # A part is selected by clicking it
    click(page, lcy_position(page, buffer))
    assert page.js(f"{LCY}.$(':selected').map(e => e.id())") == [buffer]

    # Move a belt: drag the end of Constructor 1's belt to the Versatile Framework exit
    fit(page)
    page.js(f"void {LCY}.$(':selected').unselect(); void {LCY}.edges().filter(e => e.source().id() === 'b1|Steel Beam').select()")
    page.drag(lcy_position(page, "__end|to"), lcy_position(page, framework))
    page.wait_until(belts_between("b1|Steel Beam", framework) + " === 1")
    # That exit now merges three belts, so a fourth is refused, and nothing changes
    page.js(f"void {LCY}.$(':selected').unselect(); void {LCY}.edges().filter(e => e.source().id() === 'b2|Steel Beam').select()")
    page.drag(lcy_position(page, "__end|to"), lcy_position(page, framework))
    page.wait_until("document.getElementById('toast').textContent === "
                    "'to Versatile Framework (demand) merges up to 3 belts, and has them all.'")
    assert page.js(belts_between("b2|Steel Beam", encased)) == 1

    # Nodes move, and stay where they're put
    fit(page)
    before = page.js(f"{LCY}.getElementById('b3|Steel Beam').position()")
    x, y = lcy_position(page, "b3|Steel Beam")
    page.drag((x, y), (x, y + 60))
    stored = saved(page)["logistics"]["positions"][f"{BEAM}|out"]["b3|Steel Beam"]
    assert stored["y"] > before["y"] + 20

    # Reset: back to the suggested layout, drawn as suggested
    page.js("document.getElementById('lv-reset').click()")
    layouts = f"JSON.parse(localStorage.getItem({json.dumps(KEY)})).logistics.layouts"
    page.wait_until(f"!({json.dumps(BEAM + '|out')} in {layouts})")
    assert page.js("document.getElementById('lv-warnings').textContent") == ""
    assert f"{BEAM}|out" not in saved(page)["logistics"]["positions"]

    page.send("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
    page.wait_until("document.getElementById('logistics-view').hidden")


def test_a_change_that_breaks_an_edited_layout_resets_it(page):
    open_logistics(page)
    zoom_in(page)
    page.js("document.querySelector('.lv-add[data-kind=merger]').click()")  # an edit, so the layout is stored
    page.wait_until(f"{LCY}.nodes('.merger').length === 1")
    page.js("document.getElementById('lv-back').click()")

    rows = "document.querySelectorAll('#demand-rows input[name=rates]')"
    page.js(f"{rows}[0].value = '10'; document.querySelector('#demand-form button[type=submit]').click()")
    page.wait_until("document.getElementById('toast').textContent.startsWith('Logistics reset')")
    assert f"{BEAM}|out" not in saved(page)["logistics"]["layouts"]


def test_marking_buildings_built(page):
    open_logistics(page)
    page.select_node(BEAM)
    page.js("document.getElementById('built-all-btn').click()")
    assert saved(page)["built"][BEAM]["count"] == 5
    assert page.js(f"{CY}.getElementById({json.dumps(BEAM)}).hasClass('done')")
    assert not page.js(f"{CY}.getElementById({json.dumps(BEAM + '|out')}).hasClass('done')")  # production nodes only


def test_new_plan_keeps_the_settings(page):
    open_logistics(page, {**BEAMS, "logistics": {"settings": {"belt_tier": 2, "pipe_tier": 1, "smart": False}, "layouts": {}}})
    page.js("window.confirm = () => true; document.getElementById('new-plan-btn').click()")
    assert saved(page)["items"] == []
    assert saved(page)["logistics"] == {"settings": {"belt_tier": 2, "pipe_tier": 1, "smart": False}, "layouts": {}, "positions": {}}
