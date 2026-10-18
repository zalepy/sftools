# sftools

Production planner for [Satisfactory](https://www.satisfactorygame.com/). Enter target items and rates; sftools expands the production chain into a graph of buildings that you can adjust interactively, and plans the belts, pipes, splitters and mergers too.

Simple mode (the planner without belts, with node splitting) was removed on 2026-10-17; its last version is on the branch `backup/simple-mode`. Its saved plans and files don't open here.

Live (UAT): https://sftools.onrender.com/

## Features
* **Side panel tabs**: **Planner** holds the plan-wide controls (demands, inbound production, save/load, clearing; logistics settings), **Node** what's selected in the graph (it opens when you click a node, by-product edge or logistics node), **Colors** the item colors (Define gives any item a color, × resets a built-in one or removes one you defined; Save Colors applies them), **Recipes** the preferred recipe of each item.
* **Graph visualization**: Cytoscape graph of the production chain. The Legend button in the header explains the colors and marks. Each demand target is a circle with a purple border, fed by the node that makes it (in the zoomed-in output logistics too). Inbound production nodes have a sky-blue one, and nodes with clocks set a dashed cyan one. Node text turns dark on bright node colors. The side panel can be hidden (button left of the title) to give the graph the whole width; the choice is remembered in the browser.
* **Clock speeds**: set a node's clock for all its buildings, and optionally a different one for the last building. The number of buildings is always calculated from the demand and the clocks, and the inputs follow. Power accounts for the clocks, and nodes show the power shards they need.
* **Merging**: drag one node onto another node with the same output item to combine them; unmerge from the side panel.
* **Recipe switching**: pick an alternate recipe for an individual node; nodes running an alternate are labelled "(A)". Inputs both recipes use keep their adjustments and are rescaled; inputs the new recipe doesn't use are removed with their whole branch, and new ones are added.
* **Preferred recipes**: the **Recipes** tab lists every item made by more than one recipe (ores too: node purity and miner), each with a dropdown set to its default recipe. Pick another, and every node of the item runs it, in every tab, unless a node has a recipe switched of its own (e.g. Cast Screws for all Screws). Changed ones are highlighted; filter by name or show only those; All to Default resets them. "Prefer for <item>" under a node's recipe does the same from a node. They're kept in the browser, like the colors. Unmerge keeps the merged node's own recipe on the nodes split back out.
* **Inbound production**: items supplied from outside the plan (e.g. by another factory) at a given rate, listed under the demand targets and applied with Calculate. They cover demand for the item, top down, before anything is produced; a node left with nothing to make disappears with its inputs. An inbound node (sky-blue border) shows how much is used and feeds the nodes that use it.
* **Sink**: every by-product goes to one round Sink node, on a dotted edge with its rate. The Sink counts its power (30 MW per AWESOME Sink). Fluids can't be sunk in the game: they still go to the Sink as a placeholder, so the rest of the plan calculates, but their edges turn red and the Sink gets a thick red border until you deal with them.
* **By-products as supply**: Calculate uses by-products to cover demand for the same item elsewhere in the plan (after inbound production; nodes closest to the demands first), shown as dashed sky-blue edges from the maker. Other changes (recipe switches, merges, clocks, ...) don't: a by-product that appears then goes to the Sink. Click a by-product edge to see what's made, used and sunk, and to switch between "Use as Supply" and "Send to Sink"; that choice is kept, also by later Calculates. A use that would feed a node above its own maker (a loop) isn't applied: it goes to the Sink on a red-orange edge marked "(loop)". "Solve Loop" on that edge balances it (red-orange dashed edges, "(loop, solved)"); if it can't, it stays on the Sink and the panel says so. A demand target covered entirely by inbound production or by-products stays shown, with no buildings.
* **Move Branch to Inbound** (Node tab): moves a node and its inputs to another plan. Its item becomes inbound production of this plan, at the rate its consumers take, so the node and everything under it go. Only for an item made by that one node (merge them first) that isn't a demand target of the plan. Pick the destination: Undefined (add the demand target there later), another tab, or a new tab; a tab gets the demand target, linked on the Chain tab. Undo in this plan doesn't remove the destination's demand target. (It replaces the old "Supplied from outside" recipe: a plan that still has it gets the node back on its default recipe, with a notice.)
* **Undo/redo**: the ↶ ↷ buttons in the header, or Ctrl+Z and Ctrl+Y (Ctrl+Shift+Z), step through the plan's changes: merges, recipe switches, clocks, demand edits and imports. Up to 50 steps, kept until the page is reloaded.
* **Built marks**: record how many of a node's buildings you've built in the game ("Built" in the selected node, or All Built). Done nodes fade and get a ✓; partly built ones show e.g. "6/8". When the plan grows, a done node shows what's left; after a recipe switch the old count no longer counts. Clear Built Marks resets them.
* **Plan tabs**: several plans side by side, in tabs above the graph: **+** adds one, the second button duplicates the shown one (for what-if variants), double-click a tab to rename it, ✕ closes it (asking first when it has a plan). Each tab has its own undo; logistics settings (what's unlocked) are shared by all the tabs.
* **Chain tab** (left of the plan tabs): how the plans feed each other. Each tab is a box with its inbound production on the left and its demand targets on the right. Drag from a demand target to another tab's inbound production of the same item to link them, e.g. 13 Motors from "AW" to ACU's 6 and MFG's 7; a link also records that the connection is routed in the game. One plan can feed several, or several can feed one, not both. The rates on links come from the plans (one feeding several: what each one asks for; several feeding one: what each makes), and nodes show where they don't add up: red short, blue spare (or more than needed), green matching; unlinked ones stay plain. Nothing changes a plan on its own. To pass on a by-product, the plan that makes it sets it as a demand target (covered by the by-product, no buildings added), the other as inbound production. Drag a box to move it; double-click it to open the tab. Links are saved with the tabs and in Save Book; closing a tab drops its links.
* **Save/load**: the tabs are stored in your browser. **Export Plan** downloads the shown tab's plan, **Save Book** all the tabs in one file, with the preferred recipes and your colors; **Import** opens a plan in a new tab, or a book in place of all the tabs (asking first; its preferred recipes and colors become this browser's). **New Plan** clears the shown tab (demands, inbound production and every adjustment; logistics settings and colors stay); undo brings it back.
* **Logistics**: belts, pipes, splitters and mergers for every node (`/logistics`, the old address of logistics mode, leads to the page).
  * **Settings**: the highest belt and pipe tiers unlocked, and smart/programmable splitters.
  * Each node has a small **logistics node** on each side: inputs on the left, outputs on the right, showing its number of splitters and mergers (red when something's short, dashed when you edited it). The graph's edges are belts between them, labelled with the tier they need, e.g. "36.00/m · Mk.3"; an edge that needs more than one belt of the highest tier is amber ("· 2× Mk.6").
  * **Belts per edge**: click an edge to set how many belts it is (− / +, or Default Belts), e.g. a belt to each Rotor from two Cast Screws producers instead of one shared belt with splitters. An edge whose count you set is matched belt by belt: each belt has an exit on the producer's side and an entry on the consumer's, and what the producer's layout puts on each belt arrives at that entry (e.g. Stator to Motors at 100%, 100% and 70%: 10, 10 and 7.5/min, of which the third Motor takes 7). With the default count, the edge's belts are one bundle, shared as if balanced.
  * **Push and pull**: an output side is pushed: its buildings put out all they make, and splitters share it evenly, so each exit shows what lands on its belt, amber when that's more than the other end takes (it backs up there). Only a smart splitter backs up its main outputs, once their exits have what they need. An input side is pulled: its buildings take what they need of what the entries bring.
  * Click a logistics node for a summary, then **Zoom In** to see and edit it: its buildings, entries or exits (one per belt of each edge), splitters, mergers and belts, with the rate on every belt. Buildings (or entries) stand in the left column, exits (or buildings) in the right one, splitters (rhombuses) and mergers (squares) between. A building that runs at another clock than the rest (e.g. the last, partial one) has a cyan border. On the input side the buildings are in order, each with its inputs together (Building 1's, then Building 2's, ...). Drag a node to move it (kept with the plan). The dots under a node are its free outputs: drag from one to another node to lay a belt; while you drag, the nodes that can take it turn green. Select a belt and drag one of its ends to move it. Each entry and exit is one belt: select one for − Belt / + Belt on its edge, double-click it to open the other end of that belt. Add splitters, mergers, smart splitters (overflow) and buffers; select and delete; Reset goes back to the suggested layout. Changes that don't fit (a port already used, a belt between different items, a loop) are refused.
  * **Suggested layouts**: outputs grouped by destination (whole buildings per edge, the rest merged and split, with smart splitters filling an edge that has no building of its own first; surplus backing up), an edge's belts filled up to what the consumer takes on each; inputs as a manifold, or each belt of an edge feeding its own buildings. A change to the plan that alters an edited logistics node's buildings or edges resets it to the suggested layout, with a short notice; undo brings yours back.

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
