# 045 — Move a branch to inbound production

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** [030](030-inbound-production.md), [039](039-plan-tabs.md), [040](040-chain-tab.md)

## Goal
Migrate a branch from one plan to another. A button on the selected node turns its item into inbound production of the plan it's in, so the node and everything below it disappear there. Optionally the destination plan gets the matching demand target.

## Decisions (agreed with the user, 2026-10-18)
- **Button:** "Move Branch to Inbound…" on the Node tab. Production nodes only: not on demand targets, inbound nodes, supplied-from-outside nodes or the Sink.
- **Only on fully merged nodes:** the item must be made by exactly one node in the plan, because inbound production covers the plan's demand for the item top down rather than a chosen node. Otherwise the button is disabled with the reason, e.g. "Merge all 3 Screws nodes first".
- **Not when the item is also a demand target of this plan** (e.g. the node merged into its demand circle): inbound would cover the target first. Disabled with the reason.
- **Rate:** what the node's consumers take (sum of `parent_demands`), not its building output (clock rounding can make that higher).
- **Source plan:** an inbound row for the item at that rate (added to an existing row for the item), then recalculated. Its node and inputs go away. The branch's own entries (recipe switches, clocks, merges, built marks, logistics edits) no longer match and are dropped with the usual plan notice; undo brings them back. By-products the branch made disappear too. If the rest of the plan used one as supply, the confirmation names it.
- **Destination picker:**
  - "Undefined" (default): only the inbound row. The user adds the demand target and the Chain link later.
  - An existing tab: a demand row for the item at the rate (added to its existing row for the item), plus a Chain link from it to the source. If the Chain rules refuse the link (one plan feeds several, or several feed one, not both), the rows stay and a notice says the link wasn't made. The destination tab's stored plan is changed and recalculates when opened.
  - "New tab…": a new tab with just that demand, linked on the Chain.
- **Nothing carries over** to the destination: no recipes, clocks, merges or built marks. It calculates the demand fresh, with the preferred or default recipes.
- **Afterwards:** stay on the source plan, with a notice like "Moved 15/min Motor to MFG".
- **Undo gap:** undo is per plan. Undoing in the source removes the inbound row, but the destination keeps its demand row. The confirmation warns about this.

- **Remove "Supplied from outside"** (the user's call, 2026-10-18): this feature supersedes it. Remove it as part of this ticket:
  - The recipe picker option, `OUTSIDE_SUPPLY` / `outside_supply_recipe` and `RecipeType.OUTSIDE` (calculator, recipe_type), and the "supplied from outside: no buildings" clock check.
  - The Switch Recipe hint and the legend entry (index.html). The legend's sky-blue border stays for inbound production.
  - Its tests (`test_supplied_from_outside` and the unit tests in test_api.py).
  - The docs (README, ARCHITECTURE).
  - Keep the `is_supplied` flag: the inbound node uses it (`_inbound_node`), and so do the checks that skip buildings, clocks and logistics for it.
  - **Saved plans and books** that still have `"Supplied from outside"` as a node's recipe: the server ignores it like any unknown recipe, the plan notice reports it, and the branch comes back on its default or preferred recipe. The user can then use Move Branch to Inbound. No automatic conversion: its semantics are per node, inbound's are per item.

## Notes
- Whether the node is the only one making the item: count nodes with `output_item` equal to it (by-product makers don't count). A merged node is one node.
- Chain links and tab plans live in `tabs.js` (`getBook()`, the stored plans); the demand/inbound rows in `panel.js` (`getDemands`, `setDemands`).

## Done (2026-10-18)
- Backup of master before this change: branch `backup/pre-045`.
- Removed "Supplied from outside": `OUTSIDE_SUPPLY`, `outside_supply_recipe`, `RecipeType.OUTSIDE`, `ProductionNode.is_supplied` and the checks on it (calculator, factory_graph), the recipe option, hint and legend text. `is_supplied` stays in the node data: false for production nodes, true for the inbound node. A plan that still names the recipe gets it ignored as an unknown recipe (plan notice); `test_supplied_from_outside_is_gone`.
- Node tab: "Move Branch to Inbound…" (`renderMoveBranch`, disabled with the reason), and a form with the destination and what happens, including by-products of the branch used elsewhere and the undo gap (`openMoveBranch`).
- `moveBranch` (main.js): the inbound row, recalculated; on failure the rows go back. Then the destination: a new tab named after the item (`tabs.uniqueName`) or the chosen tab's stored plan gets the demand row (added to an existing one); `chain.addLink` links it (or says why not). Toast: "Moved 2.00/min Rotor to Rotor."
- Browser tests: `test_move_branch_needs_a_single_node_that_is_not_a_demand_target`, `test_move_branch_to_a_new_tab_then_to_an_existing_one`, `test_move_branch_without_a_destination`.
