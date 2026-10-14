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
| `src/sftools/engine/logistics.py` | Logistics mode (ticket 033): each node's input/output logistics, suggested layouts, belt-flow simulation, belt tiers per edge |
| `src/sftools/api/app.py` | FastAPI app factory; serves the UI at `/` and `/healthz` |
| `src/sftools/api/routes.py`, `schemas.py` | JSON API under `/api` and its request/response models |
| `src/sftools/web/templates/index.html` | Page markup (Jinja: item list, asset version); Cytoscape + dagre from CDN |
| `src/sftools/web/static/app.css` | Styles |
| `src/sftools/web/static/js/` | ES modules: `main.js` (entry, plan actions), `api.js`, `state.js` (plan + localStorage), `graph.js` (Cytoscape), `panel.js` (sidebar) |
| `src/sftools/data/` | Scraped game data and the default node color palette |
| `scripts/scrape/` | Scrapers that regenerate `src/sftools/data/` |
| `tests/unit/` | Fast tests: engine, graph, game data, API (in-process) |
| `tests/integration/` | Browser tests: real app + headless Chrome over the DevTools protocol |
| `tests/e2e/` | For tests against live environments (none yet) |
| `tickets/` | Known issues and planned work |

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
  "splits":    {"<node_id>": 2}
}
```

`build_plan` replays the plan in a fixed order:
1. **Expand demands** (`calculate_demands`): breadth-first expansion into a tree of `ProductionNode`s, using `default_recipe_for(item)` for each item (see [ALGO.md](ALGO.md)). A node produces one item, which can be either the recipe's main product (`output1` in the data) or its by-product. **Splits** apply here, as nodes are created (`split_parts`): a node split into k parts becomes k nodes with an equal share of its demand, each expanded into its own inputs. Nodes created by a recipe switch (step 2) are split the same way.
2. **Recipe switches**, parents first. A child's ID extends its parent's ID, so sorting by ID length is enough. A switch keeps the inputs both recipes use (their nodes, and the adjustments on them, are rescaled), drops the inputs the new recipe doesn't use, with everything under them (they become dormant), and builds the new inputs as in step 1. A switch is skipped if its node doesn't exist or was dropped, or the recipe can't be resolved. The recipe name `Supplied from outside` (`OUTSIDE_SUPPLY`) is resolved to `outside_supply_recipe(item)`: no inputs, no building or power, so the switch drops the node's inputs like any other. `_set_scale` gives such a node no buildings, only its rate, and its clocks are dropped.
3. **Merges**: `FactoryGraph.apply_merge` marks the source as absorbed by the target. The merged node is one shared set of buildings; each branch keeps its own inputs, sized to its share of the merged node's demand.
4. **Clocks + propagation**: `FactoryGraph.recalculate` runs Kahn's algorithm (see [ALGO.md](ALGO.md)). Each node's buildings come from its demand and its clocks (`parse_clock_groups`, `FactoryGraph._set_scale`): one group without a count runs as many buildings as the rest of the demand needs, plus fixed groups such as the last building. Building counts are never set directly (ticket 023). `build_plan(exact=True)` gives fractional building counts instead, which the unit tests use to check that every item balances; the API always uses whole buildings.

**Inbound production** (`inbound`) is applied in step 4: `recalculate` goes top down, and each node (or merge group) of an inbound item takes what it needs from what is left of the inbound rate before its buildings are sized for the rest. Its consumers' shares shrink by the same fraction. A group left with nothing to make, and the groups under it that then need nothing, go into `FactoryGraph.unused` and aren't returned; their plan entries stay valid and apply again when the inbound rate drops. Each inbound item is returned as an extra node, `inbound:<item>`, with `inbound: {rate, used}` and the consumers it feeds in `parent_demands`. Nodes switched to "Supplied from outside" don't use inbound production.

**By-products** go to the **Sink** (ticket 024): `get_ui_data` adds a node `sink` when any shown node makes a by-product (`Recipe.other_outputs` × the node's building scale). `sink.inputs` lists each one as `{from, item, rate, fluid}`, and `sink.fluids` names the fluids (item categories LIQUIDS and GAS), which can't be sunk in the game. The Sink's buildings (one AWESOME Sink per 1200/min of solids) and power (30 MW each) are constants, as the scraped data has no AWESOME Sink. **By-products as supply** (ticket 031): `byproducts` says per node whether its by-products cover demand elsewhere (`use`) or go to the Sink (`sink`); nodes not listed get `byproducts_default`, which the UI sends as `use` only for Calculate. The response's `byproducts` is what the plan keeps (`resolved_byproduct_choices`): every choice the plan set, plus every by-product node when the default was `use`. A default `sink` isn't recorded, so a later Calculate can still use those. In `recalculate`, each used by-product's maker is ordered before every group of its item (`_order_byproduct_uses`), and covers demand after inbound production, top down, like it. A use whose ordering edges would close a cycle is left out (`byproduct_loops`) and goes to the Sink, unless its choice is `solve` (ticket 032): `recalculate` then solves those loops on fractional buildings, round by round, each round supplying what the maker made in the one before, damped when the difference grows; one more pass sets whole buildings with the settled amounts. If it doesn't settle in `LOOP_ROUNDS`, the plan is shown without those uses (`loop_settled` False). Covered demand is recorded against the node itself when the user demands it (`External Demand`), and a demanded node stays shown when there's nothing left to make; nodes under it are hidden. Each node's `byproducts` lists item, rate, choice, loop and `used` ({consumer: rate}); the Sink gets what's left.

**Logistics mode** (ticket 033): the page at `/logistics` sends `mode: "logistics"` and `logistics: {settings: {belt_tier, pipe_tier, smart}, layouts: {"<node id>|in" | "|out": layout}}`, and never splits. After `get_ui_data`, `logistics.attach_logistics` adds to each node with buildings `logistics: {in, out}`: the side's buildings (one per building, from its clock groups), entries (in, one per edge into the node) or exits (out, one per consumer, the user's demand, by-product use or the Sink), and its splitters, mergers, smart (overflow) splitters, buffers and belts, with simulated flows, warnings and `complexity` (splitters + mergers). Sides the plan doesn't list get the suggested layout (`default_layout`); a listed layout whose buildings, entries or exits changed (`fixed`) is reset and returned in `logistics_resets`. The simulation is steady state: sources push their rate, splitters share evenly among outputs that aren't backed up (water-filling), mergers share their output among inputs, overflow splitters fill main outputs first; repeated until the flows settle. Only trees (no loop-backs) for now. Each edge also gets `edge_belts` (belt or pipe, tier, count: `belts_needed`). The browser keeps logistics plans under their own localStorage key (`sf_logistics_state`) and exports them with `mode: "logistics"`.

Entries that no longer match the graph (typically from an older saved plan) are skipped and returned in `ignored` with a reason; the UI removes them from the saved plan and shows a notice. Entries on dropped inputs (an input the recipe running above it doesn't use, or anything under one) are returned with `"dropped": true`, and the UI removes them without a notice: when the input comes back, it starts as a fresh branch. A merge group runs its target's recipe, so the absorbed nodes' inputs that it doesn't use are dropped too. When a merge target is dropped, the rest of its group stays merged: those entries carry `replacement`, the new target.

**Built marks** (ticket 037) are browser-only: the plan keeps `built: {"<node id>": {count, recipe}}` and the server never sees it. Buildings needed are the node's whole buildings (with clocks) or its scale rounded up; a mark counts only while the node runs the recipe it was made for. `graph.builtStatus` computes it, and `refreshBuilt` redraws the badges (top left: a check, or "built/needed") and the `done` class (faded) without a request.

Every saved change is also an undo step (`static/js/history.js`): the history holds plan snapshots as JSON strings, and undo or redo recalculates one like any other plan. The plan is saved in localStorage (`sf_planner_state`) and can be exported to or imported from a JSON file. User changes to node colors are kept in localStorage (`sf_planner_colors`) on top of the default palette from `GET /api/colors`.

Why stateless: on a shared deployment, a single server-side graph would be shared (and overwritten) by every visitor and lost whenever the instance restarts or the free tier spins down. Rebuilding the graph takes milliseconds, so replaying the whole plan on every request costs little.

## Graph model

- **`Recipe`** (a dataclass): `product` (the main product, `output1` in the data), `byproducts` and `ingredients`, each as `(Item, rate per building)`, plus `building` and `type`. `rate_of(item)`, `produces(item)` and `generate_demands` take the item a node makes, since a node can run a recipe for its by-product.
- **`ProductionNode`**: one recipe run in some number of buildings. It stores base (1×) rates; scaled output, inputs and power are derived from `building_scale`: the sum of its buildings' clocks (`building_clocks`), or in exact mode the fractional `original_building_scale`. Base power comes from `Building.power_for(recipe)`; for buildings whose draw depends on the recipe (Particle Accelerator, Quantum Encoder, Converter) it is the midpoint of the listed range. `parent_demands` records how much each parent (or `"External Demand"` for a root) asks for.
- **`FactoryGraph`** keeps *every* node created for the plan:
  - **Merged** nodes have `absorbed_by` set. Their links move to the target (for the UI view), and `get_ui_data` hides them and lists them in the target's `constituent_ids`. `recalculate` works from the unmerged structure: a group's demand is the sum of its members', and each member's input nodes get that member's share of the group's inputs (see [ALGO.md](ALGO.md)).
  - **Dormant** nodes are dropped inputs: the recipe running above them doesn't use them. They stay in the graph but are excluded from calculation and the UI.
  - `link(parent, child)` records each link in the unmerged structure as it is made. `build_plan` resets to that structure (`_reset_structure`) and replays the merges until no more inputs are dropped. An unmerge is simply a plan without that merge.

### Node identity
Node IDs are item paths (`root_node_ids`, `child_node_id` in `engine/calculator.py`):

- **Roots** are keyed by item: `Smart Plating`. A second demand row for the same item gets `Smart Plating#2`.
- **Children** extend the parent's ID with their item: `Smart Plating__Reinforced Iron Plate__Screws`.
- **Parts of a split node**: part 1 keeps the node's ID, so its clocks, recipe and merges stay with it. The other parts get `~2`, `~3`, ...: `Smart Plating__Reinforced Iron Plate~2`, whose inputs are `Smart Plating__Reinforced Iron Plate~2__Screws` and so on. Each part is an ordinary node with its own override and recipe, and can be merged. A merged node can't be split (the UI asks to unmerge first). When parts are removed, the UI drops the entries that belonged to them.

IDs don't depend on recipes. When a node switches recipe, the inputs both recipes use keep their IDs and adjustments; see `tickets/done/022`. Merges, clocks, splits and recipe switches refer to nodes by these IDs, so they stay valid as long as the items above them don't change (see `tickets/done/016`).

Names can't contain `__`, `#` or `~`; `tests/unit/test_graph_state.py` covers the scheme.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | UI page (item list rendered into the page) |
| GET | `/logistics` | The same page in logistics mode (`data-mode="logistics"` on the body) |
| GET | `/healthz` | Liveness check for Render |
| POST | `/api/calculate` | Build the graph for a plan; returns `{"nodes": [...], "ignored": [...]}`. 422 for unknown items, 400 for a merge of different items. |
| GET | `/api/available_recipes?item_name=` | Recipes for an item (name, type, building, output rate) |
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

## Decision log

- **src layout + uv** (2026-10): an installable package, so imports and data paths don't depend on the working directory; dependencies are locked in `uv.lock`.
- **One FastAPI app serving the UI at `/` and the API at `/api`**: simplest local setup and a single Render service. If the UI ever needs a build step, its output can still be served from `/`.
- **Stateless API** (2026-10): replaced the process-global graph (`GLOBAL_STATE`), which was fine for single-user local use but not for a shared deployment. Merge, unmerge, switch-recipe and recalculate endpoints were folded into `POST /api/calculate`; `POST /api/colors` was removed.
- **Recipe product from the data** (2026-10): `output1` is the main product, and the node decides which output it produces. This replaced guessing the product from the recipe name, which failed for 38 alternates.
- **Removed the Falcon service**: a leftover from before FastAPI that was never wired up.
