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
| `src/sftools/engine/loader.py` | Parses the scraped JSON into domain models |
| `src/sftools/engine/game_data.py` | Process-wide, read-only cache of the loaded models |
| `src/sftools/engine/calculator.py` | Graph construction: `calculate_demands`, recipe switching, `build_plan` |
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
  "round_up":  true,
  "recipes":   {"<node_id>": "<recipe name>"},
  "merges":    {"<source node_id>": "<target node_id>"},
  "overrides": {"<node_id>": 3},
  "splits":    {"<node_id>": 2}
}
```

`build_plan` replays the plan in a fixed order:
1. **Expand demands** (`calculate_demands`): breadth-first expansion into a tree of `ProductionNode`s, using `default_recipe_for(item)` for each item (see [ALGO.md](ALGO.md)). A node produces one item, which can be either the recipe's main product (`output1` in the data) or its by-product. **Splits** apply here, as nodes are created (`split_parts`): a node split into k parts becomes k nodes with an equal share of its demand, each expanded into its own inputs. Nodes created by a recipe switch (step 2) are split the same way.
2. **Recipe switches**, parents first. A child's ID extends its parent's ID, so sorting by ID length is enough. A switch is skipped if its node doesn't exist, is dormant (cut off by an upstream switch), or the recipe can't be resolved.
3. **Merges**: `FactoryGraph.apply_merge` marks the source as absorbed by the target. The merged node is one shared set of buildings; each branch keeps its own inputs, sized to its share of the merged node's demand.
4. **Overrides + propagation**: `FactoryGraph.recalculate` runs Kahn's algorithm (see [ALGO.md](ALGO.md)).

Entries that no longer match the graph (typically from an older saved plan) are skipped and returned in `ignored` with a reason; the UI removes them from the saved plan and shows a notice. Entries for dormant nodes or inactive branches (under an upstream recipe that was switched away from) are kept without a report, because they apply again if that recipe is switched back.

The plan is saved in localStorage (`sf_planner_state`) and can be exported to or imported from a JSON file. User changes to node colors are kept in localStorage (`sf_planner_colors`) on top of the default palette from `GET /api/colors`.

Why stateless: on a shared deployment, a single server-side graph would be shared (and overwritten) by every visitor and lost whenever the instance restarts or the free tier spins down. Rebuilding the graph takes milliseconds, so replaying the whole plan on every request costs little.

## Graph model

- **`ProductionNode`**: one recipe run in some number of buildings. It stores base (1×) rates; scaled output, inputs and power are derived from `building_scale`, which is `user_scale` if set and otherwise `original_building_scale`. Base power comes from `Building.power_for(recipe)`; for buildings whose draw depends on the recipe (Particle Accelerator, Quantum Encoder, Converter) it is the midpoint of the listed range. `parent_demands` records how much each parent (or `"External Demand"` for a root) asks for.
- **`FactoryGraph`** keeps *every* node created for the plan:
  - **Merged** nodes have `absorbed_by` set. Their links move to the target (for the UI view), and `get_ui_data` hides them and lists them in the target's `constituent_ids`. `recalculate` works from the unmerged structure: a group's demand is the sum of its members', and each member's input nodes get that member's share of the group's inputs (see [ALGO.md](ALGO.md)).
  - **Dormant** nodes belong to a recipe that was switched away from. They stay in the graph but are excluded from calculation and the UI.
  - `link(parent, child)` records each link in the unmerged structure as it is made, and `_rebuild_structure` restores that structure and then replays the merges (unmerge). In stateless mode an unmerge is simply a plan without that merge.
  - `recalculate(overrides)` replaces all overrides when given a dict (`{}` clears them) and keeps the current ones when given `None`.

### Node identity
Node IDs are item paths (`root_node_ids`, `child_node_id` in `engine/calculator.py`):

- **Roots** are keyed by item: `Smart Plating`. A second demand row for the same item gets `Smart Plating#2`.
- **Children** extend the parent's ID with their item: `Smart Plating__Reinforced Iron Plate__Screws`.
- When the parent runs a recipe other than its default, that recipe is part of the child's ID: `Smart Plating__Reinforced Iron Plate__Alternate: Bolted Iron Plate>Screws`.
- **Parts of a split node**: part 1 keeps the node's ID, so its override, recipe and merges stay with it. The other parts get `~2`, `~3`, ...: `Smart Plating__Reinforced Iron Plate~2`, whose inputs are `Smart Plating__Reinforced Iron Plate~2__Screws` and so on. Each part is an ordinary node with its own override and recipe, and can be merged. A merged node can't be split (the UI asks to unmerge first). When parts are removed, the UI drops the entries that belonged to them.

A node's ID never depends on its own recipe, only on its ancestors' recipes. Switching a node's recipe therefore gives its inputs new IDs: adjustments below the switch reset, and the old ones apply again when the node is switched back. Merges, overrides and recipe switches refer to nodes by these IDs, so they stay valid as long as nothing above them changes (see `tickets/done/016`).

Names can't contain `__`, `>`, `#` or `~`; `tests/unit/test_graph_state.py` covers the scheme.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | UI page (item list rendered into the page) |
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
