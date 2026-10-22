# Tests

| Folder | What | Needs | Run |
|---|---|---|---|
| `unit/` | Engine, graph, game data, API (in-process `TestClient`) | Nothing; runs in about a second | `uv run pytest` (the default) |
| `integration/` | The UI in a real browser against a running app | Chrome, Chromium or Edge; starts the app on a free local port | `uv run pytest tests/integration` |

Run unit tests whenever you like. CI runs both folders on every push.

## Integration tests

`integration/conftest.py` starts `uvicorn` and a headless browser, and drives the browser over the Chrome DevTools protocol (the `websockets` package, no Selenium/Playwright). Each test gets a fresh tab with empty browser storage, and **fails if the page logs a JavaScript error or warning**. The tests skip themselves when no browser is found.

Environment variables:
- `CHROME_PATH`: the browser executable, if it isn't found automatically.
- `SFTOOLS_BASE_URL`: test an app that is already running instead of starting one. For example, to check the UAT deploy:
  ```bash
  SFTOOLS_BASE_URL=https://sftools.onrender.com uv run pytest tests/integration

  After a release, `uv run python scripts/release_check.py` does this once the site reports the pushed commit.
  ```

Useful page helpers: `page.open(url, plan)` loads the app with a saved plan, and `page.select_node(id)` opens a node's details. `page.node_position(id)` with `page.drag(start, end)` performs a real mouse drag, e.g. to merge nodes. `page.js(expr)` evaluates JavaScript, and `page.wait_until(expr)` polls it.
