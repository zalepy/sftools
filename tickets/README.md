# Tickets

## Open

| # | Title | Type | Pri | Status |
|---|-------|------|-----|--------|
| [034](034-balancers.md) | Balancers with loop-backs (logistics mode) | feature | P3 | Open |

Next when wanted: 034. Smaller ideas live in [TODO.md](../TODO.md).

## Done

Moved to [done/](done/).

| # | Title | Type | Pri | Status |
|---|-------|------|-----|--------|
| [001](done/001-project-structure-uv-src-layout.md) | Restructure: uv, src layout, single FastAPI app | chore | P1 | Done |
| [002](done/002-architecture-doc.md) | Add ARCHITECTURE.md | docs | P1 | Done |
| [003](done/003-fluid-rate-parsing.md) | Fluid rates parsed 10× too high | bug | P0 | Done |
| [004](done/004-recipe-explicit-primary-output.md) | Recipe product guessed from name | bug | P0 | Done |
| [005](done/005-default-recipe-selection.md) | Default recipe can belong to another item | bug | P0 | Done |
| [006](done/006-recalculate-wipes-overrides.md) | Merge/switch clears overrides | bug | P1 | Done |
| [007](done/007-unmerge-drops-switched-subtree.md) | Unmerge disconnects switched subtree | bug | P1 | Done |
| [008](done/008-dormancy-through-merged-links.md) | Dormancy spreads through merged links | bug | P1 | Done |
| [009](done/009-api-error-handling.md) | API validation and error responses | bug | P2 | Done |
| [010](done/010-server-global-state.md) | Shared GLOBAL_STATE across users | bug | P1 | Done |
| [011](done/011-colors-endpoint-writes-repo.md) | POST /api/colors writes repo file | bug | P2 | Done |
| [012](done/012-persist-recipe-switches.md) | Recipe switches not saved | bug | P1 | Done |
| [013](done/013-data-validation-tests.md) | Validation tests on real data | test | P1 | Done |
| [014](done/014-recipe-model-refactor.md) | Recipe model lists refactor | refactor | P3 | Done |
| [015](done/015-external-merge-unmerge-bug.md) | External-demand merge/unmerge bug | bug | P1 | Closed |
| [016](done/016-node-id-stability.md) | Node ID stability | debt | P3 | Done |
| [017](done/017-frontend-split.md) | Split index.html | refactor | P3 | Done |
| [018](done/018-ui-feature-backlog.md) | UI/feature backlog | feature | P3 | Done |
| [019](done/019-scraped-data-gaps.md) | Gaps in the scraped game data | data | P2 | Done |
| [020](done/020-merge-double-counts-inputs.md) | Merging two nodes double-counts their inputs | bug | P0 | Done |
| [021](done/021-node-splitting.md) | Node splitting | feature | P3 | Done |
| [022](done/022-recipe-switch-inputs.md) | Recipe switch: keep shared inputs, drop unused branches | feature | P2 | Done |
| [023](done/023-clock-speeds.md) | Clock speeds per node (replaces building overrides) | feature | P2 | Done |
| [024](done/024-byproducts-to-sink.md) | By-products go to a Sink node | feature | P2 | Done |
| [025](done/025-exact-recipe-rates.md) | Recipe rates rounded to two decimals | data bug | P2 | Done |
| [026](done/026-undo-redo.md) | Undo and redo of plan changes | feature | P2 | Done |
| [027](done/027-optimize-branch.md) | "Optimize branch" with preview | feature | P3 | Won't do |
| [028](done/028-belts-and-pipes.md) | Belt and pipe capacity (logistics mode) | feature | P3 | Done |
| [029](done/029-cleanup-after-clocks.md) | Cleanup: API round-up, fixed scales, legacy engine paths and tests | debt | P2 | Done |
| [030](done/030-inbound-production.md) | Inbound production | feature | P2 | Done |
| [031](done/031-byproducts-as-supply.md) | By-products count as supply | feature | P2 | Done |
| [032](done/032-solve-byproduct-loops.md) | Solve by-product loops on request | feature | P3 | Done |
| [033](done/033-logistics-mode.md) | Logistics mode (separate, advanced) | feature | P3 | Done |
| [035](done/035-legend.md) | Legend | feature | P3 | Done |
| [036](done/036-logistics-editing-issues.md) | Splitter/merger editing problems (logistics mode) | bug | P2 | Done |
| [037](done/037-built-marks.md) | Mark buildings as built | feature | P3 | Done |
| [038](done/038-node-tab.md) | Node tab in the side panel | feature | P3 | Done |
| [039](done/039-plan-tabs.md) | Plan tabs and Save Book | feature | P2 | Done |
| [040](done/040-chain-tab.md) | Chain tab: links between plans | feature | P2 | Done |
| [041](done/041-belts-per-edge.md) | Belts per edge, matched across both ends (logistics mode) | feature | P2 | Done |
| [042](done/042-push-output-sides.md) | Output sides pushed, input sides pulled (logistics mode) | feature | P2 | Done |
| [043](done/043-preferred-recipes.md) | Preferred recipes | feature | P2 | Done |
| [044](done/044-define-colors.md) | Define item colors | feature | P3 | Done |
| [045](done/045-move-branch-to-inbound.md) | Move a branch to inbound production; Supplied from outside removed | feature | P2 | Done |
| [046](done/046-notes.md) | Notes per node and per plan | feature | P3 | Done |
| [047](done/047-fit-last-clock.md) | Fit the last building's clock to the demand | feature | P3 | Done |
| [048](done/048-reorder-tabs.md) | Reorder plan tabs by drag and drop | feature | P3 | Done |
| [049](done/049-user-guide.md) | User guide, in the repo and in the app | docs | P2 | Done |
| [050](done/050-ci.md) | CI, lint for bugs, and the release check | chore | P2 | Done |
| [051](done/051-js-unit-tests.md) | Unit tests for the front end's pure logic | test | P3 | Done |
| [052](done/052-split-panel-and-main.md) | Split panel.js and main.js; guidance on where code goes | refactor | P3 | Done |
| [053](done/053-eslint.md) | ESLint for bugs, in CI | chore | P3 | Done |
| [054](done/054-split-factory-graph.md) | Split factory_graph.py: calculation and UI view | refactor | P3 | Done |
| [055](done/055-burn-residue.md) | Burn Heavy Oil Residue for power | feature | P2 | Done |
| [056](done/056-reference-layouts.md) | Reference layouts: crude oil to Turbofuel power | feature | P3 | Done |
