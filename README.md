# sftools

Production planner for [Satisfactory](https://www.satisfactorygame.com/). Enter target items and rates; sftools expands the production chain into a graph of buildings that you can adjust interactively.

Live (UAT): https://sftools.onrender.com/

## Features
* **Graph visualization**: Cytoscape graph of the production chain. The Legend button in the header explains the colors and marks. Nodes you demand have a purple border, nodes supplied from outside a sky-blue one, and nodes with clocks set a dashed cyan one. Node text turns dark on bright node colors. The side panel can be hidden (button left of the title) to give the graph the whole width; the choice is remembered in the browser.
* **Clock speeds**: set a node's clock for all its buildings, and optionally a different one for the last building. The number of buildings is always calculated from the demand and the clocks, and the inputs follow. Power accounts for the clocks, and nodes show the power shards they need.
* **Merging**: drag one node onto another node with the same output item to combine them; unmerge from the side panel.
* **Splitting**: split a node into equal parts from the side panel, e.g. to build them in different places. Each part has its own inputs, clocks and recipe. Dragging one part onto another merges them back.
* **Recipe switching**: pick an alternate recipe for an individual node; nodes running an alternate are labelled "(A)". Inputs both recipes use keep their adjustments and are rescaled; inputs the new recipe doesn't use are removed with their whole branch, and new ones are added.
* **Inbound production**: items supplied from outside the plan (e.g. by another factory) at a given rate, listed under the demand targets and applied with Calculate. They cover demand for the item, top down, before anything is produced; a node left with nothing to make disappears with its inputs. An inbound node (sky-blue border) shows how much is used and feeds the nodes that use it.
* **Sink**: every by-product goes to one round Sink node, on a dotted edge with its rate. The Sink counts its power (30 MW per AWESOME Sink). Fluids can't be sunk in the game: they still go to the Sink as a placeholder, so the rest of the plan calculates, but their edges turn red and the Sink gets a thick red border until you deal with them.
* **By-products as supply**: Calculate uses by-products to cover demand for the same item elsewhere in the plan (after inbound production; nodes closest to the demands first), shown as dashed sky-blue edges from the maker. Other changes (recipe switches, merges, clocks, ...) don't: a by-product that appears then goes to the Sink. Click a by-product edge to see what's made, used and sunk, and to switch between "Use as Supply" and "Send to Sink"; that choice is kept, also by later Calculates. A use that would feed a node above its own maker (a loop) isn't applied: it goes to the Sink on an amber edge marked "(loop)". "Solve Loop" on that edge balances it (amber dashed edges, "(loop, solved)"); if it can't, it stays on the Sink and the panel says so. A demand target covered entirely by inbound production or by-products stays shown, with no buildings.
* **Supplied from outside**: the last entry in a node's recipe list marks that one node as supplied from outside, whatever its rate. It keeps its rate and loses its buildings, inputs and clocks.
* **Undo/redo**: the ↶ ↷ buttons in the header, or Ctrl+Z and Ctrl+Y (Ctrl+Shift+Z), step through the plan's changes: merges, splits, recipe switches, clocks, demand edits and imports. Up to 50 steps, kept until the page is reloaded.
* **Built marks**: record how many of a node's buildings you've built in the game ("Built" in the selected node, or All Built). Done nodes fade and get a ✓; partly built ones show e.g. "6/8". When the plan grows, a done node shows what's left; after a recipe switch the old count no longer counts. Works in both modes; Clear Built Marks resets them.
* **Save/load**: the plan is stored in your browser and can be exported to or imported from JSON.
* **Logistics mode** (`/logistics`, link at the top right): the same planner, also planning belts, pipes, splitters and mergers. Its plans are its own (saved and exported separately; each mode refuses the other's files), and it has no splits.
  * **Settings**: the highest belt and pipe tiers unlocked, and smart/programmable splitters.
  * Each node has a small **logistics node** on each side: inputs on the left, outputs on the right, showing its number of splitters and mergers (red when something's short, dashed when you edited it). The graph's edges are belts between them, labelled with the tier they need, e.g. "36.00/m · Mk.3"; an edge that needs more than one belt of the highest tier is amber ("· 2× Mk.6").
  * Click a logistics node for a summary, then **Zoom In** to see and edit it: its buildings, entries or exits (one per edge), splitters, mergers and belts, with the rate on every belt. Drag from one node to another to lay a belt; add splitters, mergers, smart splitters (overflow) and buffers; select and delete; Reset goes back to the suggested layout. Changes that don't fit (a port already used, a belt between different items, a loop) are refused.
  * **Suggested layouts**: outputs grouped by destination (whole buildings per exit, the rest merged and split, surplus backing up); inputs as a manifold. A change to the plan that alters an edited logistics node's buildings or edges resets it to the suggested layout, with a short notice; undo brings yours back.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how it works, [ALGO.md](ALGO.md) for the calculation, [tickets/](tickets/README.md) for known issues and planned work, and [TODO.md](TODO.md) for smaller ideas.

## Local development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                            # create .venv with app + dev dependencies
uv run uvicorn sftools.api.app:app --reload        # http://127.0.0.1:8000
uv run pytest                                      # unit tests (about a second)
uv run pytest tests/integration                    # browser tests (needs Chrome/Edge)
```

See [tests/README.md](tests/README.md) for the test layout.

API docs are generated by FastAPI at http://127.0.0.1:8000/docs.

### Updating game data
The JSON under `src/sftools/data/` is scraped from [Satisfactory-Calculator](https://satisfactory-calculator.com):

```bash
uv run --group scrape python scripts/scrape/pull_all_data.py
```

See [scripts/scrape/README.md](scripts/scrape/README.md) for details.

### Pre-push check
To run the tests before every push, create `.git/hooks/pre-push`:
```bash
#!/bin/sh
uv run pytest -q || { echo "Tests failed! Push aborted."; exit 1; }
```

## Deployment (Render)

The service is described in [render.yaml](render.yaml):

| Setting | Value |
|---|---|
| Build command | `pip install uv && uv sync --frozen --no-dev` |
| Start command | `.venv/bin/python -m uvicorn sftools.api.app:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/healthz` |
| Python version | from `.python-version` |

If the service was created by hand in the Render dashboard (not as a Blueprint), copy these settings into **Settings → Build & Deploy**.
