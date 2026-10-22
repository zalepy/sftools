# Working on sftools

A Satisfactory production planner: FastAPI server (`src/sftools/`), plain ES-module front end (`src/sftools/web/static/js/`), no build step. How it fits together: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Decisions: [tickets/](tickets/README.md).

## Workflow

- Discuss a feature first and record it in a ticket (`tickets/NNN-name.md`, listed in `tickets/README.md`); build it on a branch.
- "merge push": merge the branch into master with `--no-ff`, push, then run `uv run python scripts/release_check.py` (waits until the live demo runs the commit, then runs the browser tests against it).
- A bug found along the way (e.g. behind a flaky test) gets fixed and a test that reproduces it deterministically.

## Code structure

Files stay small and do one thing. `scripts/check_sizes.py` warns in CI about any file over **500 lines**; past ~400, look for the split.

### Front end (`static/js/`)

| Where | What goes there | May touch the DOM? |
|---|---|---|
| `main.js` | Wiring only: `addEventListener` calls that hand off to actions, and startup. No logic. | yes |
| `actions/` | What the user does to the plan: change state, ask the server (`requestPlan`), save (an undo step), redraw. One module per area: `plan.js` (core, plan-wide), `node.js`, `tabs.js`, `logistics.js`, `notes.js`, `preferences.js`. | through `panel/` |
| `panel/` | The side panel, one module per tab or section: reads its inputs, renders what it's given. Doesn't call the server or save. `common.js` holds `$`, `nodeLabel` and other shared bits. | yes |
| `graph.js`, `logistics.js`, `chain.js` | The Cytoscape views: the plan graph, the zoomed-in logistics view, the chain of tabs. | yes |
| `state.js`, `tabs.js`, `history.js` | The plan in memory and in localStorage, the book of tabs, undo. | `tabs.js` draws the tab bar |
| Pure modules: `clocks.js`, `node-info.js`, `logistics-placement.js` | Calculations and text from data. **No DOM, no Cytoscape, no imports of modules that touch them**, so Node can import them: they're unit-tested in `tests/js/`. | no |

Rules of thumb:
- A new feature: its actions in `actions/<area>.js`, its panel section in `panel/<section>.js`, its wiring in `main.js`. A new area gets a new module, not a bigger old one.
- A calculation (a rule, a formula, a text built from data) goes in a pure module with a unit test in `tests/js/`, even if only one place uses it. Keep DOM code thin around it.
- Modules import what they use by name (`import { showToast } from './panel/messages.js'`); the arrows go `main → actions → panel/graph/state → pure`. Nothing imports `main.js` or `actions/` from below.
- Comments say why, in plain words, with the ticket number for a feature's decisions.

### Back end (`src/sftools/`)

`domain/` (game data models, the factory graph), `engine/` (calculation, logistics simulation, loading data), `api/` (FastAPI routes; stateless: everything comes in the request). Same size rule; one concern per module. `engine/logistics.py` is over on purpose (one algorithm, see docs/ALGO.md).

## Tests and checks

```
uv run pytest                          # Python unit tests (~1 s)
node --test "tests/js/*.test.mjs"      # JS unit tests of the pure modules
uv run pytest tests/integration        # browser tests (Chrome/Edge via CDP, ~1-2 min)
uvx ruff check src tests scripts       # Python lint (bug rules only)
npx eslint@10.12.0 src/sftools/web/static/js tests/js   # JS lint (bug rules only)
uv run python scripts/check_sizes.py   # files over 500 lines
```

- Lint is for bugs, not style: don't add style rules or reformat code. A deliberate exception gets a `# noqa: <rule>` / `// eslint-disable-next-line <rule>` with the reason.
- `tests/unit/test_api.py::test_module_imports_resolve` checks every JS import names an export that exists; run the unit tests after moving code between modules.
- UI behavior is tested in `tests/integration/` through the real page; logic is tested in `tests/js/` or `tests/unit/`.
