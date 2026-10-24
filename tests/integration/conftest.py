"""
Fixtures for browser tests: a local app server and a headless Chromium (Chrome or Edge) driven
over the DevTools protocol. Tests are skipped when no browser is found.

Environment:
    SFTOOLS_BASE_URL  test an already running app (e.g. the UAT deploy) instead of starting one
    CHROME_PATH       browser executable, if it isn't found automatically
"""
import contextlib
import itertools
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest
from websockets.sync.client import connect

BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]
BROWSER_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge"]


def find_browser():
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"] if Path(os.environ["CHROME_PATH"]).exists() else None
    for name in BROWSER_NAMES:
        if path := shutil.which(name):
            return path
    return next((path for path in BROWSER_CANDIDATES if Path(path).exists()), None)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            return urllib.request.urlopen(url, timeout=2).read()
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(url)


@pytest.fixture(scope="session")
def base_url():
    if url := os.environ.get("SFTOOLS_BASE_URL"):
        yield url.rstrip("/") + "/"
        return
    port = free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "sftools.api.app:app", "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(f"http://127.0.0.1:{port}/healthz")
        yield f"http://127.0.0.1:{port}/"
    finally:
        server.terminate()
        server.wait(timeout=10)


@pytest.fixture(scope="session")
def browser():
    executable = find_browser()
    if not executable:
        pytest.skip("no Chrome/Chromium/Edge found (set CHROME_PATH)")
    port = free_port()
    profile = tempfile.mkdtemp(prefix="sftools-browser-")
    process = subprocess.Popen(
        [executable, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
         "--no-first-run", "--no-default-browser-check", "--window-size=1400,900", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(f"http://127.0.0.1:{port}/json/version")
        yield port
    finally:
        process.terminate()
        process.wait(timeout=10)
        shutil.rmtree(profile, ignore_errors=True)


class Page:
    """A browser tab: evaluate JS, drive the mouse, and collect JS errors and dialogs."""

    def __init__(self, port):
        self._port = port
        request = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT")
        self._target = json.loads(urllib.request.urlopen(request).read())
        self._stack = contextlib.ExitStack()
        self._ws = self._stack.enter_context(connect(self._target["webSocketDebuggerUrl"], max_size=None))
        self._ids = itertools.count(1)
        self.errors = []
        self.dialogs = []
        self.paused = []  # requests held by hold_requests, until release_requests
        for domain in ("Runtime", "Log", "Page"):
            self.send(f"{domain}.enable")

    def close(self):
        self._stack.close()
        urllib.request.urlopen(f"http://127.0.0.1:{self._port}/json/close/{self._target['id']}")

    def _handle(self, message):
        method, params = message.get("method"), message.get("params", {})
        if method == "Runtime.exceptionThrown":
            details = params["exceptionDetails"]
            self.errors.append(details.get("exception", {}).get("description") or details.get("text"))
        elif method == "Runtime.consoleAPICalled" and params["type"] in ("error", "warning"):
            self.errors.append(f"console.{params['type']}: " + " ".join(
                str(arg.get("value", arg.get("description"))) for arg in params["args"]))
        elif method == "Log.entryAdded" and params["entry"]["level"] == "error":
            self.errors.append("log: " + params["entry"]["text"])
        elif method == "Fetch.requestPaused":
            self.paused.append(params["requestId"])
        elif method == "Page.javascriptDialogOpening":
            self.dialogs.append(params["message"])
            self.send("Page.handleJavaScriptDialog", wait=False, accept=True)

    def send(self, method, wait=True, **params):
        message_id = next(self._ids)
        self._ws.send(json.dumps({"id": message_id, "method": method, "params": params}))
        while wait:
            message = json.loads(self._ws.recv())
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result")
            self._handle(message)

    def wait(self, seconds):
        """Lets the page work (requests, rendering) while still collecting events."""
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                self._handle(json.loads(self._ws.recv(timeout=0.05)))
            except TimeoutError:
                pass

    def wait_until(self, expression, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.js(expression):
                return
            self.wait(0.1)
        raise AssertionError(f"timed out waiting for: {expression}")

    def js(self, expression):
        result = self.send("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        if result.get("exceptionDetails"):
            raise RuntimeError(result["exceptionDetails"].get("exception", {}).get("description"))
        return result["result"].get("value")

    def open(self, url, plan=None, key="sf_logistics_state"):
        """Loads the app with an empty browser state, or with `plan` as the saved plan (under `key`)."""
        if plan is not None:
            plan = {"mode": "logistics", **plan}  # the only mode (simple mode plans are refused)
        self.send("Page.navigate", url=url)
        self.wait_until("document.readyState === 'complete'")
        self.js("localStorage.clear()")
        if plan is not None:
            self.js(f"localStorage.setItem({json.dumps(key)}, JSON.stringify({json.dumps(plan)}))")
        self.send("Page.reload")
        self.wait(0.3)
        self.wait_until("document.readyState === 'complete' && !document.getElementById('calculate-btn').disabled")
        if plan is not None and plan.get("items"):
            self.wait_until("document.getElementById('cy')._cyreg.cy.nodes().length > 0", timeout=30)

    def hold_requests(self, url_pattern):
        """Holds the page's requests to URLs matching `url_pattern` (e.g. '*/api/power_items') in `paused`."""
        self.send("Fetch.enable", patterns=[{"urlPattern": url_pattern, "requestStage": "Request"}])

    def release_requests(self):
        for request_id in self.paused:
            self.send("Fetch.continueRequest", requestId=request_id)
        self.paused = []
        self.send("Fetch.disable")

    # --- App helpers ---

    def saved_plan(self, key="sf_logistics_state"):
        return self.js(f"JSON.parse(localStorage.getItem({json.dumps(key)}))")

    def node_ids(self):
        return self.js("document.getElementById('cy')._cyreg.cy.nodes().map(n => n.id())")

    def select_node(self, node_id):
        self.js(f"import('/static/js/graph.js').then(g => g.reselectNode({json.dumps(node_id)}))")
        self.wait_until(f"document.getElementById('detail-id').textContent === {json.dumps(node_id)}")

    def node_position(self, node_id):
        return self.js(f"""(() => {{
            const container = document.getElementById('cy');
            const box = container.getBoundingClientRect();
            const p = container._cyreg.cy.getElementById({json.dumps(node_id)}).renderedPosition();
            return [box.left + p.x, box.top + p.y];
        }})()""")

    def drag(self, start, end, steps=10):
        (x0, y0), (x1, y1) = start, end
        self.send("Input.dispatchMouseEvent", type="mouseMoved", x=x0, y=y0)
        self.send("Input.dispatchMouseEvent", type="mousePressed", x=x0, y=y0, button="left", clickCount=1)
        for step in range(1, steps + 1):
            self.send("Input.dispatchMouseEvent", type="mouseMoved", button="left", buttons=1,
                      x=x0 + (x1 - x0) * step / steps, y=y0 + (y1 - y0) * step / steps)
            self.wait(0.02)
        self.send("Input.dispatchMouseEvent", type="mouseReleased", x=x1, y=y1, button="left", clickCount=1)


@pytest.fixture
def page(browser, base_url):
    """A fresh tab; fails the test if the page logged JS errors or warnings."""
    tab = Page(browser)
    tab.base_url = base_url
    yield tab
    errors = list(tab.errors)
    tab.close()
    assert not errors, f"JS errors/warnings: {errors}"
