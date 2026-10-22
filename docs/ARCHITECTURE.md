# Architecture

sftools is a production planner for Satisfactory. A user enters target items and rates, and the app expands them into a graph of production nodes (recipe × building count). The user can then adjust the graph: override scales, merge nodes, and switch recipes.

```
 satisfactory-calculator.com
            │  scripts/scrape (offline, manual)
            ▼
 src/sftools/data/*.json ──► engine/loader ──► domain models (Item, Recipe, Building)
                                                    │  loaded once per process (engine/game_data)
 browser (static/js modules + Cytoscape)                   ▼
   plan state in localStorage ──POST /api/calculate──► engine/calculator.build_plan ──► FactoryGraph
            ▲                                                                              │
            └──────────────────────── {"nodes": [...]} ◄── FactoryGraph.get_ui_data() ◄────┘
```

## Repository layout

| Path | Purpose |
|---|---|
| `src/sftools/config.py` | Paths (data dir, templates) and env overrides |
| `src/sftools/domain/enums/` | Building/item categories, recipe type, demand type |
| `src/sftools/domain/models/` | `Item`, `Recipe`, `Building`, `Demand`, `ProductionNode`, `FactoryGraph` |
| `src/sftools/engine/loader.py` | Parses the scraped JSON into domain models. The scraped rates are rounded to two decimals, so it recomputes them from each recipe's cycle time (`cycle_seconds`, ticket 025) |
| `src/sftools/engine/game_data.py` | Process-wide, read-only cache of the loaded models |
| `src/sftools/engine/calculator.py` | Graph construction: `calculate_demands`, recipe switching, `build_plan` |
| `src/sftools/engine/logistics.py` | Logistics (ticket 033): each node's input/output logistics, suggested layouts, belt-flow simulation, belt tiers per edge |
| `src/sftools/api/app.py` | FastAPI app factory; serves the UI at `/` and `/healthz` |
| `src/sftools/api/routes.py`, `schemas.py` | JSON API under `/api` and its request/response models |
| `src/sftools/api/guide.py`, `src/sftools/web/guide/` | The user guide: `USER_GUIDE.md` and its `images/` (made by `scripts/screenshots.py`), rendered to HTML once at startup for the Guide panel. GitHub shows the same file. |
| `src/sftools/web/templates/index.html` | Page markup (Jinja: item list, asset version); Cytoscape + dagre from CDN |
| `src/sftools/web/static/app.css` | Styles |
| `src/sftools/web/static/js/` | ES modules: `main.js` (entry, plan actions), `api.js`, `state.js` (plan + localStorage), `tabs.js` (plan tabs, the book), `history.js` (undo), `graph.js` (Cytoscape), `panel.js` (sidebar), `notes.js` (notes, the note box), `guide.js` (the Guide panel and the "?" links) |
| `src/sftools/data/` | Scraped game data and the default node color palette |
| `scripts/scrape/` | Scrapers that regenerate `src/sftools/data/` |
| `scripts/screenshots.py`, `scripts/release_check.py` | The guide's screenshots (with the browser-test harness); the post-deploy check (waits for the commit on `/healthz`, then runs the browser tests) |
| `tests/unit/` | Fast tests: engine, graph, game data, API (in-process) |
| `tests/integration/` | Browser tests: real app + headless Chrome over the DevTools protocol |
| `tickets/` | Known issues and planned work |
| `docs/` | This file and ALGO.md: docs about the code, never served (the user guide, which the app serves, lives in the package) |
| `.github/workflows/` | CI: lint, JS syntax, unit and browser tests on every push |

Dependency direction: `api → engine → domain`. `domain` imports nothing from the other packages.

## State model

**The server is stateless.** The only data it holds is the read-only game data, which is loaded once per process.

The browser owns the **plan** and sends all of it on every change:

```json
{
  "demands":   [{"item": "Smart Plating", "rate": 2}],
  "inbound":   [{"item": "Iron Ingot", "rate": 60}],
  "byproducts": {"<node_id>": "use" | "sink" | "solve"},
  "recipes":   {"<node_id>": "<recipe name>"},
  "merges":    {"<source node_id>": "<target node_id>"},
  "clocks":    {"<node_id>": [{"clock": 1.0}, {"count": 1, "clock": 2.0}]},
  "logistics": {"settings": {"belt_tier": 6, "pipe_tier": 2, "smart": true}, "layouts": {}}
}
```

`build_plan` replays the plan in a fixed order:
1. **Expand demands** (`calculate_demands`): breadth-first expansion into a tree of `ProductionNode`s, using the plan's `preferred` recipe for the item (ticket 043; `recipe_for`, unknown ones left out by `resolve_preferred`), else `default_recipe_for(item)` (see [ALGO.md](ALGO.md)); new branches after a recipe switch do the same. A node produces one item, which can be either the recipe's main product (`output1` in the data) or its by-product.
2. **Recipe switches**, parents first. A child's ID extends its parent's ID, so sorting by ID length is enough. A switch keeps the inputs both recipes use (their nodes, and the adjustments on them, are rescaled), drops the inputs the new recipe doesn't use, with everything under them (they become dormant), and builds the new inputs as in step 1. A switch is skipped if its node doesn't exist or was dropped, or the recipe can't be resolved.
3. **Merges**: `FactoryGraph.apply_merge` marks the source as absorbed by the target. The merged node is one shared set of buildings; each branch keeps its own inputs, sized to its share of the merged node's demand.
4. **Clocks + propagation**: `FactoryGraph.recalculate` runs Kahn's algorithm (see [ALGO.md](ALGO.md)). Each node's buildings come from its demand and its clocks (`parse_clock_groups`, `FactoryGraph._set_scale`): one group without a count runs as many buildings as the rest of the demand needs, plus fixed groups such as the last building. Building counts are never set directly (ticket 023). `build_plan(exact=True)` gives fractional building counts instead, which the unit tests use to check that every item balances; the API always uses whole buildings.

**Inbound production** (`inbound`) is applied in step 4: `recalculate` goes top down, and each node (or merge group) of an inbound item takes what it needs from what is left of the inbound rate before its buildings are sized for the rest. Its consumers' shares shrink by the same fraction. A group left with nothing to make, and the groups under it that then need nothing, go into `FactoryGraph.unused` and aren't returned; their plan entries stay valid and apply again when the inbound rate drops. Each inbound item is returned as an extra node, `inbound:<item>`, with `inbound: {rate, used}` and the consumers it feeds in `parent_demands`. Move Branch to Inbound (ticket 045) is browser-only: it adds an inbound row for the node's item and, in the destination tab, a demand row and a Chain link.

**By-products** go to the **Sink** (ticket 024): `get_ui_data` adds a node `sink` when any shown node makes a by-product (`Recipe.other_outputs` × the node's building scale). `sink.inputs` lists each one as `{from, item, rate, fluid}`, and `sink.fluids` names the fluids (item categories LIQUIDS and GAS), which can't be sunk in the game. The Sink's buildings (one AWESOME Sink per 1200/min of solids) and power (30 MW each) are constants, as the scraped data has no AWESOME Sink. **By-products as supply** (ticket 031): `byproducts` says per node whether its by-products cover demand elsewhere (`use`) or go to the Sink (`sink`); nodes not listed get `byproducts_default`, which the UI sends as `use` only for Calculate. The response's `byproducts` is what the plan keeps (`resolved_byproduct_choices`): every choice the plan set, plus every by-product node when the default was `use`. A default `sink` isn't recorded, so a later Calculate can still use those. In `recalculate`, each used by-product's maker is ordered before every group of its item (`_order_byproduct_uses`), and covers demand after inbound production, top down, like it. A use whose ordering edges would close a cycle is left out (`byproduct_loops`) and goes to the Sink, unless its choice is `solve` (ticket 032): `recalculate` then solves those loops on fractional buildings, round by round, each round supplying what the maker made in the one before, damped when the difference grows; one more pass sets whole buildings with the settled amounts. If it doesn't settle in `LOOP_ROUNDS`, the plan is shown without those uses (`loop_settled` False). Covered demand is recorded against the node itself when the user demands it (`External Demand`), and a demanded node stays shown when there's nothing left to make; nodes under it are hidden. Each node's `byproducts` lists item, rate, choice, loop and `used` ({consumer: rate}); the Sink gets what's left.

**Logistics** (ticket 033; simple mode, without it, was removed on 2026-10-17 and is kept on the branch `backup/simple-mode`): the page sends `logistics: {settings: {belt_tier, pipe_tier, smart}, layouts: {"<node id>|in" | "|out": layout}, edges: {"<producer>><consumer>|<item>": belts}}`. After `get_ui_data`, `logistics.attach_logistics` adds to each node with buildings `logistics: {in, out}`: the side's buildings (one per building, from its clock groups), entries (in, one per belt of each edge into the node) or exits (out, one per belt of each edge to a consumer, the user's demand, by-product use or the Sink; ids `x|<target>|<item>`, then `|2`, `|3`...), and its splitters, mergers, smart (overflow) splitters, buffers and belts, with simulated flows, warnings and `complexity` (splitters + mergers). Sides the plan doesn't list get the suggested layout (`default_layout`); a listed layout whose buildings, entries or exits changed (`fixed`) is reset and returned in `logistics_resets`. The simulation is steady state: sources push their rate, mergers share their output among inputs, overflow splitters fill main outputs first; repeated until the flows settle. An input side is pulled: splitters share evenly among outputs that aren't backed up (water-filling), buildings take up to their rate. An output side is pushed (ticket 042): splitters share by belt room only (`room`, every sink taking all it gets), exits report all they get (more than their edge's rate shows how the layout splits it), and only overflow splitters back up their main outputs by `accept` (the exits of an edge taking its rate between them). Only trees (no loop-backs) for now. Each entry and exit takes one belt; `complexity` counts splitters and mergers. Each edge also gets `edge_belts` (belt or pipe, tier, count, the count its rate `needed`, and its `key`): its count is the plan's `edges` entry, or the fewest its rate needs (`belts_needed`). The sides are simulated together (tickets 041, 042): the output sides first, then the input sides with what each belt brings. An edge whose count the plan sets is matched belt by belt (the entry brings what its exit gets, and the exit shows what the entry takes as `limit`); an edge with the default count is a bundle (what its exits get together is shared over its entries as they take it, any more evenly up to a belt's capacity, over rounds until that settles). The exits of an edge share its rate. Suggested layouts follow that order: the input sides first, then the output sides, each matched belt filled up to what its entry takes. Warnings skip shortfalls below 0.005/min (`SHORT`). Where the nodes of a zoomed-in side are drawn is browser-only, in the plan's `logistics.positions` (`"<key>": {node id: {x, y}}`): columns by default, kept once the user moves a node or edits the side, dropped on Reset or a reset. The browser keeps plans under the localStorage keys of the former logistics mode (`sf_logistics_state`, `sf_logistics_book`) and marks plans and files with `mode: "logistics"`; simple mode plans (marked `simple`, or with no mode) are refused.

Entries that no longer match the graph (typically from an older saved plan) are skipped and returned in `ignored` with a reason; the UI removes them from the saved plan and shows a notice. Entries on dropped inputs (an input the recipe running above it doesn't use, or anything under one) are returned with `"dropped": true`, and the UI removes them without a notice: when the input comes back, it starts as a fresh branch. A merge group runs its target's recipe, so the absorbed nodes' inputs that it doesn't use are dropped too. When a merge target is dropped, the rest of its group stays merged: those entries carry `replacement`, the new target.

**Built marks** (ticket 037) are browser-only: the plan keeps `built: {"<node id>": {count, recipe}}` and the server never sees it. Buildings needed are the node's whole buildings (with clocks) or its scale rounded up; a mark counts only while the node runs the recipe it was made for. `graph.builtStatus` computes it, and `refreshBuilt` redraws the badges (top left: a check, or "built/needed") and the `done` class (faded) without a request.

**Fit the last building** (ticket 047) is client-side: `panel.fitLastClock(node)` works from `ideal_building_scale` (the demand in buildings at 100%) and returns clock groups `[{clock: 1}, {count: 1, clock}]` (the last clock rounded up to 4 decimals of a percent), which `main.fitClock` applies like Apply Clock Speeds. The server then gets the building count from those clocks as usual.

**Notes** (ticket 046) are browser-only too: the plan keeps `notes: {"<node id>": text}` and `planNote`. Node ids are path-based, so a note stays with its node through recipe switches; `main.dropGoneNotes` drops the notes of nodes no longer in the graph on every save (undo restores them, as notes are in the snapshot). `notes.js` keeps what each text box was filled with to tell unsaved edits (`main.leaveNotes` asks before they go) and shows the hovered or else selected node's note in `#note-box`, over the legend. `switchRecipe` and preferred-recipe changes append a dated line to the notes of nodes whose recipe changed.

Every saved change is also an undo step (`static/js/history.js`): the history holds plan snapshots as JSON strings, and undo or redo recalculates one like any other plan; each plan tab has its own history (in memory). Plans live in tabs (ticket 039, `static/js/tabs.js`): the book `{tabs: [{id, name, plan}], active}` is saved in localStorage (`sf_logistics_book`); the active tab's plan is also kept under the plan's key (`sf_logistics_state`), as before tabs, and a plan found there without a book becomes the first tab. Tab ids are stable (renaming keeps them). A plan can be exported to or imported from a JSON file (imported into a new tab); Save Book writes the book (`{mode, tabs, active, chain, preferred, colors}`), and importing one replaces all the tabs. Logistics settings are shared by the tabs: switching keeps them, an imported plan or book brings its own. The server only ever sees the active tab's plan. The chain tab (ticket 040, `static/js/chain.js`) is drawn from the book alone: supplies are each tab's demand targets, needs its inbound production; `book.chain = {links: [{from: {tab, item}, to: {tab, item}}], positions: {tab id: {x, y}}}` holds the user's links and where the boxes are. Links join the same item, across tabs, and a group of joined links has one supply or one need (no many to many). Link rates are derived: one supply to several needs, each need's rate; several supplies to one need, each supply's rate; one to one, the smaller. Links whose ends are no longer in the plans are kept but not drawn; closing a tab drops its links. User changes to node colors are kept in localStorage (`sf_planner_colors`) on top of the default palette from `GET /api/colors`; preferred recipes (`{item: recipe}`, ticket 043) in `sf_planner_recipes`, sent as `preferred` with every request and set on the Recipes tab (from `GET /api/recipe_choices`: every item made by more than one recipe, with its default). Both are global (not per plan), saved in books and set from an imported one.

Why stateless: on a shared deployment, a single server-side graph would be shared (and overwritten) by every visitor and lost whenever the instance restarts or the free tier spins down. Rebuilding the graph takes milliseconds, so replaying the whole plan on every request costs little.

## Graph model

- **`Recipe`** (a dataclass): `product` (the main product, `output1` in the data), `byproducts` and `ingredients`, each as `(Item, rate per building)`, plus `building` and `type`. `rate_of(item)`, `produces(item)` and `generate_demands` take the item a node makes, since a node can run a recipe for its by-product.
- **`ProductionNode`**: one recipe run in some number of buildings. It stores base (1×) rates; scaled output, inputs and power are derived from `building_scale`: the sum of its buildings' clocks (`building_clocks`), or in exact mode the fractional `original_building_scale`. Base power comes from `Building.power_for(recipe)`; for buildings whose draw depends on the recipe (Particle Accelerator, Quantum Encoder, Converter) it is the midpoint of the listed range. `parent_demands` records how much each parent (or `"External Demand"` for a root) asks for. The serialized node also has `external_demand`: what the demand rows ask of it (or of its merge group), even where inbound production covers it; the page draws each demanded item as a circle, `demand|<item>`, fed by these nodes.
- **`FactoryGraph`** keeps *every* node created for the plan:
  - **Merged** nodes have `absorbed_by` set. Their links move to the target (for the UI view), and `get_ui_data` hides them and lists them in the target's `constituent_ids`. `recalculate` works from the unmerged structure: a group's demand is the sum of its members', and each member's input nodes get that member's share of the group's inputs (see [ALGO.md](ALGO.md)).
  - **Dormant** nodes are dropped inputs: the recipe running above them doesn't use them. They stay in the graph but are excluded from calculation and the UI.
  - `link(parent, child)` records each link in the unmerged structure as it is made. `build_plan` resets to that structure (`_reset_structure`) and replays the merges until no more inputs are dropped. An unmerge is simply a plan without that merge.

### Node identity
Node IDs are item paths (`root_node_ids`, `child_node_id` in `engine/calculator.py`):

- **Roots** are keyed by item: `Smart Plating`. A second demand row for the same item gets `Smart Plating#2`.
- **Children** extend the parent's ID with their item: `Smart Plating__Reinforced Iron Plate__Screws`.

IDs don't depend on recipes. When a node switches recipe, the inputs both recipes use keep their IDs and adjustments; see `tickets/done/022`. Merges, clocks and recipe switches refer to nodes by these IDs, so they stay valid as long as the items above them don't change (see `tickets/done/016`).

Names can't contain `__`, `#` or `~`; `tests/unit/test_graph_state.py` covers the scheme.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | UI page (item list rendered into the page) |
| GET | `/logistics` | Redirects to `/` (the old address of logistics mode) |
| GET | `/healthz` | Liveness check for Render |
| GET | `/guide` | The user guide as an HTML fragment (a contents list, then the text); heading ids match GitHub's, so `#section` links and the "?" links (`data-guide`) work in both |
| GET | `/guide/images/...` | The guide's screenshots (only the images: the Markdown itself isn't served) |
| POST | `/api/calculate` | Build the graph for a plan; returns `{"nodes": [...], "ignored": [...]}`. 422 for unknown items, 400 for a merge of different items. |
| GET | `/api/available_recipes?item_name=` | Recipes for an item (name, type, building, output rate) |
| GET | `/api/recipe_choices` | Items made by more than one recipe: `[{item, default, recipes}]` (Recipes tab) |
| GET | `/api/colors` | Default item → color palette |
| GET | `/static/...` | CSS and JS; `Cache-Control: no-cache`, and the page adds `?v=<hash>` to the URLs |
| GET | `/docs` | OpenAPI UI (generated by FastAPI) |

## Running and deploying

| | Local | Render (UAT, https://sftools.onrender.com/) |
|---|---|---|
| Install | `uv sync` | `pip install uv && uv sync --frozen --no-dev` |
| Run | `uv run uvicorn sftools.api.app:app --reload` | `.venv/bin/python -m uvicorn sftools.api.app:app --host 0.0.0.0 --port $PORT` |
| Python | `.python-version` | `.python-version` |
| Config | `SFTOOLS_DATA_DIR` (optional) | same; see `render.yaml` |

The UI and API come from one process at the same origin, so CORS isn't needed and there is nothing to deploy separately.

`/healthz` returns `{"status": "ok", "commit": ...}`: the commit Render deployed (its `RENDER_GIT_COMMIT` variable), or `"local"`. Render deploys every push to master. `scripts/release_check.py` polls `/healthz` until it reports the pushed commit, then runs the browser tests against the site, so they never run against the previous deploy or mid-swap, not even for docs-only pushes.

CI (`.github/workflows/tests.yml`, on every push): `ruff check` with bug-finding rules only (pyflakes and bugbear, `[tool.ruff.lint]` in `pyproject.toml`; no style rules, no formatter), `node --check` on each JS module, the unit tests, and the browser tests in headless Chrome. It reports on the commit; there's no commit hook or branch protection.

## Decision log

- **src layout + uv** (2026-10): an installable package, so imports and data paths don't depend on the working directory; dependencies are locked in `uv.lock`.
- **One FastAPI app serving the UI at `/` and the API at `/api`**: simplest local setup and a single Render service. If the UI ever needs a build step, its output can still be served from `/`.
- **Stateless API** (2026-10): replaced the process-global graph (`GLOBAL_STATE`), which was fine for single-user local use but not for a shared deployment. Merge, unmerge, switch-recipe and recalculate endpoints were folded into `POST /api/calculate`; `POST /api/colors` was removed.
- **Recipe product from the data** (2026-10): `output1` is the main product, and the node decides which output it produces. This replaced guessing the product from the recipe name, which failed for 38 alternates.
- **Removed the Falcon service**: a leftover from before FastAPI that was never wired up.
