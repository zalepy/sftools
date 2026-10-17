# 043 — Preferred recipes

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** [005](done/005-default-recipe-selection.md), [012](done/012-persist-recipe-switches.md), [022](done/022-recipe-switch-inputs.md)

## Problem
Every new node runs the default recipe for its item (`default_recipe_for`: basic first). A recipe chosen on a node is kept for that node id only, so the same choice has to be made again on every node of that item, and on every node that appears later: after Calculate, a recipe switch that adds a branch, or an unmerge. Example: Cast Screw chosen on a merged Screws node; after Unmerge the other Screws nodes are back on Screw (they never had a choice of their own).

## Decision
- **Preferred recipe per item**, global like the colors (all tabs and plans in the browser), stored in `localStorage` (`sf_planner_recipes`).
- **Order**: the node's own choice, then the item's preferred recipe, then the default.
- **Sent with each calculation** (`preferred: {item: recipe}`), used by the server wherever it picks a default recipe. An unknown recipe, or one that doesn't make the item, is ignored.
- **Books carry them**: exported books include the preferred recipes and the colors; importing a book that has them sets them (as the colors already are global).
- **Unmerge**: the nodes split back out keep the merged node's own recipe choice, when it has one.

## Plan
- Engine: `preferred` threads from the request to wherever `default_recipe_for` is used for a new node.
- Node panel, next to the recipe: "Prefer for <item>" (or "Preferred" when it is, with a way back to the default). A note when nodes keep their own choice: "3 nodes keep their own recipe".
- Colors tab gets a Recipes list: the items with a preferred recipe, each with a reset.
- A node's own choice that equals the preferred recipe is dropped (so it follows later changes).

## Done (2026-10-17)
- `preferred` in the request; `resolve_preferred` keeps the ones that exist and make their item; `recipe_for` is used by `calculate_demands` and `expand_new_subtree` (new branches after a recipe switch).
- Browser: `sf_planner_recipes`; "Prefer for <item>" / "Use Default Recipe" under Switch Recipe, with how many nodes keep a recipe of their own; Preferred Recipes list at the top of the Colors tab (✕ to remove). Preferring drops the node choices equal to it in the plan shown.
- Unmerge copies the merged node's own recipe to the nodes split back out.
- Save Book writes `preferred` and `colors` (the user's changes); importing a book sets them.
- Preferences apply live: changing one changes every tab's nodes of that item that have no recipe of their own, when next calculated.
