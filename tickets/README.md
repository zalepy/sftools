# Tickets

| # | Title | Type | Pri | Status |
|---|-------|------|-----|--------|
| [001](001-project-structure-uv-src-layout.md) | Restructure: uv, src layout, single FastAPI app | chore | P1 | Done |
| [002](002-architecture-doc.md) | Add ARCHITECTURE.md | docs | P1 | Done |
| [003](003-fluid-rate-parsing.md) | Fluid rates parsed 10× too high | bug | P0 | Open |
| [004](004-recipe-explicit-primary-output.md) | Recipe product guessed from name | bug | P0 | Open |
| [005](005-default-recipe-selection.md) | Default recipe can belong to another item | bug | P0 | Open |
| [006](006-recalculate-wipes-overrides.md) | Merge/switch clears overrides | bug | P1 | Mitigated |
| [007](007-unmerge-drops-switched-subtree.md) | Unmerge disconnects switched subtree | bug | P1 | Mitigated |
| [008](008-dormancy-through-merged-links.md) | Dormancy spreads through merged links | bug | P1 | Open |
| [009](009-api-error-handling.md) | API validation and error responses | bug | P2 | Mostly done |
| [010](010-server-global-state.md) | Shared GLOBAL_STATE across users | bug | P1 | Done |
| [011](011-colors-endpoint-writes-repo.md) | POST /api/colors writes repo file | bug | P2 | Done |
| [012](012-persist-recipe-switches.md) | Recipe switches not saved | bug | P1 | Done |
| [013](013-data-validation-tests.md) | Validation tests on real data | test | P1 | Open |
| [014](014-recipe-model-refactor.md) | Recipe model lists refactor | refactor | P3 | Open |
| [015](015-external-merge-unmerge-bug.md) | External-demand merge/unmerge bug | bug | P1 | Re-check |
| [016](016-node-id-stability.md) | Node ID stability | debt | P3 | Open |
| [017](017-frontend-split.md) | Split index.html | refactor | P3 | Open |
| [018](018-ui-feature-backlog.md) | UI/feature backlog | feature | P3 | Open |

Suggested next: 013 with 003/004/005 (data correctness) → 015 re-check → 008 → the rest.
