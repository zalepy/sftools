# 045 — Move a branch to inbound production

**Type:** feature · **Priority:** P2 · **Status:** Open (designed, implementation on hold) · **Related:** [030](done/030-inbound-production.md), [039](done/039-plan-tabs.md), [040](done/040-chain-tab.md)

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

## Notes
- Whether the node is the only one making the item: count nodes with `output_item` equal to it (by-product makers don't count). A merged node is one node.
- Chain links and tab plans live in `tabs.js` (`getBook()`, the stored plans); the demand/inbound rows in `panel.js` (`getDemands`, `setDemands`).
- "Supplied from outside" (a recipe choice) already removes a single node's branch, but the Chain tab can't see it. This feature uses inbound production so the plans can be linked.
