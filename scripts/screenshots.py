"""
Takes the user guide's screenshots (src/sftools/web/guide/images/) with the browser-test harness:
starts the app and a headless Chrome, loads example plans and captures each shot. Rerun it after UI
changes to refresh them all.

    uv run python scripts/screenshots.py
"""
import base64
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "integration"))

from conftest import Page, find_browser, free_port, wait_for  # noqa: E402

IMAGES = ROOT / "src" / "sftools" / "web" / "guide" / "images"
WINDOW = (1400, 900)

FRAMES = {"items": ["Modular Frame"], "rates": [10], "clocks": {}, "merges": {}, "recipes": {}}
PLATES = {"mode": "logistics", "items": ["Reinforced Iron Plate"], "rates": [15], "inbound": [],
          "clocks": {}, "merges": {}, "recipes": {}}
FRAMES_FED = {"mode": "logistics", "items": ["Modular Frame"], "rates": [10],
              "inbound": [{"item": "Reinforced Iron Plate", "rate": 15}], "clocks": {}, "merges": {}, "recipes": {}}
BOOK = {
    "tabs": [{"id": "plates", "name": "Plates", "plan": PLATES}, {"id": "frames", "name": "Frames", "plan": FRAMES_FED}],
    "active": "frames",
    "chain": {"links": [{"from": {"tab": "plates", "item": "Reinforced Iron Plate"},
                         "to": {"tab": "frames", "item": "Reinforced Iron Plate"}}], "positions": {}},
}


def capture(page, name, selector=None):
    """Saves the window, or just the element matching `selector`, as images/<name>.png."""
    params = {"format": "png"}
    if selector:
        box = page.js(f"""(() => {{
            const r = document.querySelector({json.dumps(selector)}).getBoundingClientRect();
            return {{ x: r.left, y: r.top, width: r.width, height: r.height }};
        }})()""")
        params["clip"] = {**box, "scale": 1}
    data = page.send("Page.captureScreenshot", **params)["data"]
    path = IMAGES / f"{name}.png"
    path.write_bytes(base64.b64decode(data))
    print(f"{path.relative_to(ROOT)}: {path.stat().st_size // 1024} KB")


def capture_graph(page, name, graph, margin=30):
    """Saves just the part of the graph area with the graph's elements in it."""
    box = page.js(f"""(() => {{
        const container = document.getElementById({json.dumps(graph)});
        const outer = container.getBoundingClientRect();
        const b = container._cyreg.cy.elements().renderedBoundingBox();
        const x = Math.max(0, outer.left + b.x1 - {margin}), y = Math.max(0, outer.top + b.y1 - {margin});
        return {{ x, y, width: Math.min(outer.right, outer.left + b.x2 + {margin}) - x,
                  height: Math.min(outer.bottom, outer.top + b.y2 + {margin}) - y }};
    }})()""")
    data = page.send("Page.captureScreenshot", format="png", clip={**box, "scale": 1})["data"]
    path = IMAGES / f"{name}.png"
    path.write_bytes(base64.b64decode(data))
    print(f"{path.relative_to(ROOT)}: {path.stat().st_size // 1024} KB")


def fit(page, graph="cy"):
    page.js(f"document.getElementById({json.dumps(graph)})._cyreg.cy.fit(undefined, 30), true")
    page.wait(0.5)


def overview(page, url):
    """The whole plan, with the side panel hidden to give the graph the room."""
    page.open(url, FRAMES)
    page.js("document.getElementById('panel-toggle').click()")
    page.wait(0.5)
    fit(page)
    capture_graph(page, "overview", "cy")


def node(page, url):
    """The Iron Plate node selected: the Node tab, and the graph zoomed in around the node."""
    page.open(url, FRAMES)
    plate = "Modular Frame__Reinforced Iron Plate__Iron Plate"
    page.select_node(plate)
    page.js(f"""(() => {{
        const cy = document.getElementById('cy')._cyreg.cy;
        const node = cy.getElementById({json.dumps(plate)});
        node.select();
        cy.zoom(1.1);
        cy.center(node);
        return true;
    }})()""")
    page.wait(0.5)
    capture(page, "node")


def logistics(page, url):
    page.open(url, FRAMES)
    page.js("import('/static/js/graph.js').then(g => g.selectLogistics('Modular Frame__Reinforced Iron Plate', 'in'))")
    page.wait_until("getComputedStyle(document.getElementById('logistics-details')).display === 'block'")
    page.js("document.getElementById('logistics-zoom-btn').click()")
    page.wait_until("!document.getElementById('logistics-view').hidden && document.getElementById('lcy')._cyreg.cy.nodes().length > 0")
    page.wait(0.8)
    fit(page, "lcy")
    capture(page, "logistics", ".graph-container")


def chain(page, url):
    page.open(url, BOOK, key="sf_logistics_book")
    page.wait_until("document.querySelectorAll('.plan-tab').length === 2")
    page.js("document.getElementById('chain-tab-btn').click()")
    page.wait_until("!document.getElementById('chain-view').hidden && document.getElementById('ccy')._cyreg.cy.nodes().length > 0")
    page.wait(0.8)
    fit(page, "ccy")
    capture_graph(page, "chain", "ccy")


def main():
    executable = find_browser()
    if not executable:
        sys.exit("No Chrome/Chromium/Edge found (set CHROME_PATH).")
    IMAGES.mkdir(parents=True, exist_ok=True)
    port, debug_port = free_port(), free_port()
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "sftools.api.app:app", "--port", str(port)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    browser = subprocess.Popen(
        [executable, "--headless=new", f"--remote-debugging-port={debug_port}",
         f"--user-data-dir={ROOT / '.pytest_cache' / 'screenshots-profile'}", "--no-first-run",
         "--no-default-browser-check", f"--window-size={WINDOW[0]},{WINDOW[1]}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = f"http://127.0.0.1:{port}/"
        wait_for(url + "healthz")
        wait_for(f"http://127.0.0.1:{debug_port}/json/version")
        page = Page(debug_port)
        page.send("Emulation.setDeviceMetricsOverride", width=WINDOW[0], height=WINDOW[1], deviceScaleFactor=1, mobile=False)
        try:
            for shot in (overview, node, logistics, chain):
                shot(page, url)
        finally:
            page.close()
        if page.errors:
            sys.exit(f"JS errors: {page.errors}")
    finally:
        browser.terminate()
        server.terminate()


if __name__ == "__main__":
    main()
