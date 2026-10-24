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
            └─────────────────────── {"nodes": [...]} ◄── graph_view.ui_nodes(graph) ◄─────┘
```

## Repository layout

| Path | Purpose |
|---|---|
| `src/sftools/config.py` | Paths (data dir, templates) and env overrides |
| `src/sftools/domain/enums/` | Building/item categories, recipe type, demand type |
| `src/sftools/domain/models/` | `Item`, `Recipe`, `Building`, `Demand`, `ProductionNode`, `FactoryGraph` (the calculation), `residue` (burning Heavy Oil Residue left over), `power` (the generators), `graph_view` (what the UI gets from it) |
| `src/sftools/engine/loader.py` | Parses the scraped JSON into domain models. The scraped rates are rounded to two decimals, so it recomputes them from each recipe's cycle time (`cycle_seconds`, ticket 025) |
| `src/sftools/engine/game_data.py` | Process-wide, read-only cache of the loaded models |
| `src/sftools/engine/calculator.py` | Graph construction: `calculate_demands`, recipe switching, `build_plan` |
| `src/sftools/engine/supply.py` | Supply-driven power plans: the inbound as the limit (`build_supply_plan`); every plan's passes for water and branches (`build_powered_plan`) |
| `src/sftools/engine/branches.py` | Branches made from by-products (`find_branches`, `fitted_clocks`) |
| `src/sftools/engine/logistics.py` | Logistics (ticket 033): each node's input/output logistics, suggested layouts, belt-flow simulation, belt tiers per edge |
| `src/sftools/api/app.py` | FastAPI app factory; serves the UI at `/` and `/healthz` |
| `src/sftools/api/routes.py`, `schemas.py` | JSON API under `/api` and its request/response models |
| `src/sftools/api/guide.py`, `src/sftools/web/guide/` | The user guide: `USER_GUIDE.md` and its `images/` (made by `scripts/screenshots.py`), rendered to HTML once at startup for the Guide panel. GitHub shows the same file. |
| `src/sftools/web/templates/index.html` | Page markup (Jinja: item list, asset version); Cytoscape + dagre from CDN |
| `src/sftools/web/static/app.css` | Styles |
| `src/sftools/web/static/js/` | ES modules, layered as in [CLAUDE.md](../CLAUDE.md) ("Code structure"): `main.js` (wiring, startup); `actions/` (what the user does to the plan: `plan.js` requests, renders and saves, plus `node.js`, `tabs.js`, `logistics.js`, `notes.js`, `preferences.js`); `panel/` (the side panel, one module per tab or section); `graph.js` + `graph-style.js` (Cytoscape), `logistics.js` (the zoomed-in view), `chain.js` (the chain tab); `api.js`, `state.js` (plan + localStorage), `tabs.js` (plan tabs, the book), `history.js` (undo), `notes.js` (notes, the note box), `guide.js` (the Guide panel and the "?" links), `layouts.js` (the Layouts panel); pure modules, unit-tested in `tests/js/`: `clocks.js`, `node-info.js`, `logistics-placement.js`, `layout-svg.js` (draws a reference layout) |
| `src/sftools/data/` | Scraped game data and the default node color palette |
| `scripts/scrape/` | Scrapers that regenerate `src/sftools/data/` |
| `scripts/screenshots.py`, `scripts/release_check.py` | The guide's screenshots (with the browser-test harness); the post-deploy check (waits for the commit on `/healthz`, then runs the browser tests) |
| `tests/unit/` | Fast tests: engine, graph, game data, API (in-process) |
| `tests/js/` | Unit tests of the pure JS modules (`node --test`, no packages) |
| `tests/integration/` | Browser tests: real app + headless Chrome over the DevTools protocol |
| `tickets/` | Known issues and planned work |
| `docs/` | This file and ALGO.md: docs about the code, never served (the user guide, which the app serves, lives in the package) |
| `.github/workflows/` | CI: lint, file sizes, unit and browser tests on every push |
| `CLAUDE.md` | How to work on the code: workflow, where new code goes, the checks |

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
  "logistics": {"settings": {"belt_tier": 6, "pipe_tier": 2, "smart": true}, "layouts": {}},
  "supply_limit": false
}
```

`build_plan` replays the plan in a fixed order:
1. **Expand demands** (`calculate_demands`): breadth-first expansion into a tree of `ProductionNode`s, using the plan's `preferred` recipe for the item (ticket 043; `recipe_for`, unknown ones left out by `resolve_preferred`), else `default_recipe_for(item)` (see [ALGO.md](ALGO.md)); new branches after a recipe switch do the same. A node produces one item, which can be either the recipe's main product (`output1` in the data) or its by-product.
2. **Recipe switches**, parents first. A child's ID extends its parent's ID, so sorting by ID length is enough. A switch keeps the inputs both recipes use (their nodes, and the adjustments on them, are rescaled), drops the inputs the new recipe doesn't use, with everything under them (they become dormant), and builds the new inputs as in step 1. A switch is skipped if its node doesn't exist or was dropped, or the recipe can't be resolved.
3. **Merges**: `FactoryGraph.apply_merge` marks the source as absorbed by the target. The merged node is one shared set of buildings; each branch keeps its own inputs, sized to its share of the merged node's demand.
4. **Clocks + propagation**: `FactoryGraph.recalculate` runs Kahn's algorithm (see [ALGO.md](ALGO.md)). Each node's buildings come from its demand and its clocks (`parse_clock_groups`, `FactoryGraph._set_scale`): one group without a count runs as many buildings as the rest of the demand needs, plus fixed groups such as the last building. Building counts are never set directly (ticket 023). `build_plan(exact=True)` gives fractional building counts instead, which the unit tests use to check that every item balances; the API always uses whole buildings.

**Inbound production** (`inbound`) is applied in step 4: `recalculate` goes top down, and each node (or merge group) of an inbound item takes what it needs from what is left of the inbound rate before its buildings are sized for the rest. Its consumers' shares shrink by the same fraction. A group left with nothing to make, and the groups under it that then need nothing, go into `FactoryGraph.unused` and aren't returned; their plan entries stay valid and apply again when the inbound rate drops. Each inbound item is returned as an extra node, `inbound:<item>`, with `inbound: {rate, used}` and the consumers it feeds in `parent_demands`. Move Branch to Inbound (ticket 045) is browser-only: it adds an inbound row for the node's item and, in the destination tab, a demand row and a Chain link.

**By-products** go to the **Sink** (ticket 024): `graph_view.ui_nodes` adds a node `sink` when any shown node makes a by-product (`Recipe.other_outputs` × the node's building scale). `sink.inputs` lists each one as `{from, item, rate, fluid, waste, loop}`, and `sink.fluids` names the fluids (item categories LIQUIDS and GAS) and `sink.waste` the nuclear waste (ticket 057), which can't be sunk in the game. The Sink's buildings (one AWESOME Sink per 1200/min of solids) and power (30 MW each) are constants, as the scraped data has no AWESOME Sink. **By-products as supply** (ticket 031): `byproducts` says per node whether its by-products cover demand elsewhere (`use`) or go to the Sink (`sink`); nodes not listed get `byproducts_default`, which the UI sends as `use` only for Calculate. The response's `byproducts` is what the plan keeps (`resolved_byproduct_choices`): every choice the plan set, plus every by-product node when the default was `use`. A default `sink` isn't recorded, so a later Calculate can still use those. In `recalculate`, each used by-product's maker is ordered before every group of its item (`_order_byproduct_uses`), and covers demand after inbound production, top down, like it. A use whose ordering edges would close a cycle is left out (`byproduct_loops`) and goes to the Sink, unless its choice is `solve` (ticket 032): `recalculate` then solves those loops on fractional buildings, round by round, each round supplying what the maker made in the one before, damped when the difference grows; one more pass sets whole buildings with the settled amounts. If it doesn't settle in `LOOP_ROUNDS`, the plan is shown without those uses (`loop_settled` False). Covered demand is recorded against the node itself when the user demands it (`External Demand`), and a demanded node stays shown when there's nothing left to make; nodes under it are hidden. Each node's `byproducts` lists item, rate, choice, loop and `used` ({consumer: rate}); the Sink gets what's left.

**Heavy Oil Residue is burned** (ticket 055; `domain/models/residue.py`): the Sink can't take fluids, so the residue left after its uses goes to a Refinery running Residual Fuel, the node `burn`. `build_plan` adds it when a node makes residue as a by-product; it isn't part of the tree, so `_propagate` leaves it out and `residue.burn` sizes it after everything else (with its own clocks), recording the residue as a use of it (`used: {"burn": rate}`) and its Fuel as `parent_demands: {"generators": rate}`. With nothing left over it goes into `unused`. `power.generator_nodes` adds the Fuel Generators (`generators`), shaped like the Sink: ⌈Fuel / 20⌉ at 100%, no clocks (the last ones are underfed and burn with gaps, so the count follows the residue), power the average the Fuel gives (Fuel/min × 12.5 MW, positive as it's generated), and `generators: {fuel, fed, power, water, fuels: [{item, rate, fed, count}]}`. The generators are constants in `power.GENERATORS`. In logistics, the Generators have an input side only (see below for the others). The by-product choice stays `use`/`sink`/`solve`; for residue the UI calls `sink` "Burn for Power".

**Reference layouts** (ticket 056): fixed builds to copy, apart from the plans. Each is a data file, `static/layouts/<id>.json`, listed in `static/layouts/index.json`, on a grid of squares: `buildings` ({label, x, y, recipe, clock, from and into: the traces they take from and feed}), `traces` (pipes and belts: {id, name, item, kind, tier, color, paths of grid points, running `totals`}), `labels` (text, or with a color a round marker), `table` (the numbers by step; a row with a `count` is a supply built elsewhere, e.g. the Compacted Coal: `count` buildings of its recipe), `note` and `power` (what the build draws, as built: {what, building, count, clock, base MW, mw}, turned into the power note by `layout-svg.js`). `layout-svg.js` draws it (belts under pipes, then buildings and labels, with `<title>` tooltips); `layouts.js` shows it in a drawer like the guide's. `tests/unit/test_layouts.py` checks the numbers against the game data: the table against the buildings' recipes and clocks, each pipe's totals against what's put in, its tier, the generators against the fuel's energy, and each power row against its buildings' draw at its clock.

**Fuel by-products are burned** (ticket 058; `power.burn_fuel_byproducts`, called by `recalculate` after the residue): what's left of a by-product that is a fuel (`power.FUELS`), after its uses, is recorded as a use by its generators (`used: {"coal-generators": rate}`), so the Sink gets none of it, unless it's solid and the plan records `sink` for its node (`power.burns`; a default `sink` burns). The choice `burn` is "don't use as supply" for any by-product, like `sink`. Each by-product says `burn` (what's left is burned), `fuel` and `burned` (the rate). `power.generator_nodes` counts those uses with the demanded fuels and the residue's Fuel; the maker's output side gets an exit to the generators. Coal Generators and Nuclear Power Plants need water, known only once the plan is calculated: `supply.build_powered_plan`, which every plan goes through, calculates again with Water roots for them (`with_water`; roots in `graph.generator_roots`, pointed at the generators by `generator_nodes`). In a limited plan, a demanded fuel made by no building and covered entirely by by-products is left out of the nodes.

**Make from a by-product** (ticket 059; `engine/branches.py`): by-product choices are per node (`"<node>"`, all its by-products) or per node and item (`"<node>|<item>"`, which wins; `FactoryGraph.byproduct_choice(node, item)`, `recorded_choice`), parsed by `calculator.parse_byproduct_choices`. `{"choice": "make", "recipe", "to": "sink" | "supply"}` (`MAKE`, kept per item, with a recipe that takes the item; a fluid product is always a supply) covers demand like `use`, and what's left after the plan's uses feeds a branch: a root `<maker>~<item>` running that recipe (`build_plan(branches=...)`, `calculate_demands` with a recipe per branch root), demanded at what that much of the by-product makes. Its input of the by-product is covered by the maker, so that input's node and its subtree are unused; its other inputs are expanded as usual. Its clock is fitted (`fitted_clocks`: as many buildings as needed at 100%, all at one clock). What's left is known only once the plan is calculated, so `build_powered_plan` calculates again (at most `PASSES`) until the branches and the generators' water settle (`settled`). In the view, the branch root has `made_from: {maker, item, recipe, to}`; for `sink` its output is `parent_demands.sink` and a Sink input with `made: true`, for `supply` it keeps its `External Demand` (a circle marked supply). The response's `made` ([{item, rate, from}]) is saved in the plan (`made`) for the Chain tab (`supply-info.chainEnds`), the first calculated numbers a plan keeps. `GET /api/recipes_using` lists the recipes that take an item.

**Supply-driven power plans** (ticket 057; `engine/supply.py`, `domain/models/power.py`): when the demands are only fuels (`power.FUELS`) and there is inbound production (`supply.eligible`), the response has `supply` (`{active: false}`, null otherwise), and the page offers **Use inbound as the limit** (`supply_limit`, saved in the plan as `supplyLimit`). With it, `build_supply_plan` builds the plan twice. A probe at the demand rates as given, exact, with every inbound row covering all it's asked (`COVER_ALL`), reads what the plan asks of each row (`FactoryGraph.item_demand`: each item's demand before inbound or by-products cover it). The smallest rate ÷ ask scales the demands (so their rates are only ratios) for the plan itself, whole buildings as usual, which can ask a little more than the limit. Raw inbound rows (`supply.is_raw`: made by a recipe with no ingredients) only set the limit and are left out of that plan, so its extraction nodes get them; the others stay inbound production. Coal Generators and Nuclear Power Plants need water: `with_water` adds a Water root per kind (`power.water_demands`), and both kinds of roots are recorded in `graph.generator_roots` ({root id: generators id}). `power.generator_nodes` points those roots at their generators (their `External Demand` becomes `parent_demands[<generators id>]`, `external_demand` 0, so no demand circle, and a by-product covering a fuel's demand is re-keyed to the generators), and adds one node per kind (`generators`, `coal-generators`, `nuclear-plants`) with the residue's Fuel joining the Fuel Generators. Nuclear waste is the plants' by-product (`waste: true`), for the Sink. `supply` then says `{active, limit, factor, demands, rows: [{item, rate, used, raw, limit, unused}], power: {gross, net}}`. In logistics (`_generator_sides`), each fuel goes to the generators burning it and water to all of them, each building taking its share (the last of a fuel underfed), and waste leaves on an output side. `GET /api/power_items` gives the page the fuels and the raw items, so it offers the checkbox as the rows change and draws the Chain tab without the server (`supply-info.chainEnds`: a limited plan gives no fuel and needs only its non-raw inbound rows).

**Logistics** (ticket 033; simple mode, without it, was removed on 2026-10-17 and is kept on the branch `backup/simple-mode`): the page sends `logistics: {settings: {belt_tier, pipe_tier, smart}, layouts: {"<node id>|in" | "|out": layout}, edges: {"<producer>><consumer>|<item>": belts}}`. After `ui_nodes`, `logistics.attach_logistics` adds to each node with buildings `logistics: {in, out}`: the side's buildings (one per building, from its clock groups), entries (in, one per belt of each edge into the node) or exits (out, one per belt of each edge to a consumer, the user's demand, by-product use or the Sink; ids `x|<target>|<item>`, then `|2`, `|3`...), and its splitters, mergers, smart (overflow) splitters, buffers and belts, with simulated flows, warnings and `complexity` (splitters + mergers). Sides the plan doesn't list get the suggested layout (`default_layout`); a listed layout whose buildings, entries or exits changed (`fixed`) is reset and returned in `logistics_resets`. The simulation is steady state: sources push their rate, mergers share their output among inputs, overflow splitters fill main outputs first; repeated until the flows settle. An input side is pulled: splitters share evenly among outputs that aren't backed up (water-filling), buildings take up to their rate. An output side is pushed (ticket 042): splitters share by belt room only (`room`, every sink taking all it gets), exits report all they get (more than their edge's rate shows how the layout splits it), and only overflow splitters back up their main outputs by `accept` (the exits of an edge taking its rate between them). Only trees (no loop-backs) for now. Each entry and exit takes one belt; `complexity` counts splitters and mergers. Each edge also gets `edge_belts` (belt or pipe, tier, count, the count its rate `needed`, and its `key`): its count is the plan's `edges` entry, or the fewest its rate needs (`belts_needed`). The sides are simulated together (tickets 041, 042): the output sides first, then the input sides with what each belt brings. An edge whose count the plan sets is matched belt by belt (the entry brings what its exit gets, and the exit shows what the entry takes as `limit`); an edge with the default count is a bundle (what its exits get together is shared over its entries as they take it, any more evenly up to a belt's capacity, over rounds until that settles). The exits of an edge share its rate. Suggested layouts follow that order: the input sides first, then the output sides, each matched belt filled up to what its entry takes. Warnings skip shortfalls below 0.005/min (`SHORT`). Where the nodes of a zoomed-in side are drawn is browser-only, in the plan's `logistics.positions` (`"<key>": {node id: {x, y}}`): columns by default, kept once the user moves a node or edits the side, dropped on Reset or a reset. The browser keeps plans under the localStorage keys of the former logistics mode (`sf_logistics_state`, `sf_logistics_book`) and marks plans and files with `mode: "logistics"`; simple mode plans (marked `simple`, or with no mode) are refused.

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
  - **Merged** nodes have `absorbed_by` set. Their links move to the target (for the UI view), and `ui_nodes` hides them and lists them in the target's `constituent_ids`. `recalculate` works from the unmerged structure: a group's demand is the sum of its members', and each member's input nodes get that member's share of the group's inputs (see [ALGO.md](ALGO.md)).
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

CI (`.github/workflows/tests.yml`, on every push): `ruff check` with bug-finding rules only (pyflakes and bugbear, `[tool.ruff.lint]` in `pyproject.toml`; no style rules, no formatter), ESLint with bug-finding rules only (`eslint.config.mjs`, run with `npx`: no `package.json`), `scripts/check_sizes.py` (warns about files over 500 lines), the Python and JS unit tests, and the browser tests in headless Chrome. Every step runs even when an earlier one fails. It reports on the commit; there's no commit hook or branch protection.

## Decision log

- **src layout + uv** (2026-10): an installable package, so imports and data paths don't depend on the working directory; dependencies are locked in `uv.lock`.
- **One FastAPI app serving the UI at `/` and the API at `/api`**: simplest local setup and a single Render service. If the UI ever needs a build step, its output can still be served from `/`.
- **Stateless API** (2026-10): replaced the process-global graph (`GLOBAL_STATE`), which was fine for single-user local use but not for a shared deployment. Merge, unmerge, switch-recipe and recalculate endpoints were folded into `POST /api/calculate`; `POST /api/colors` was removed.
- **Recipe product from the data** (2026-10): `output1` is the main product, and the node decides which output it produces. This replaced guessing the product from the recipe name, which failed for 38 alternates.
- **Removed the Falcon service**: a leftover from before FastAPI that was never wired up.
