# 040 — Chain tab: links between plans

**Type:** feature · **Priority:** P2 · **Status:** Open · **Related:** [039](039-plan-tabs.md)

## Goal
A special tab that shows how plans feed each other, as a graph, and records which of those connections exist (routed in game). Needs tabs (039). Discussed 2026-10-16.

Example: tab "AW" demands 13 Motors; "ACU" has 6 Motors as inbound production, "MFG" 7. In the chain tab the user draws edges from AW:Motors to ACU:Motors and MFG:Motors; AW's 13 against 6 + 7 is balanced.

## Design (as agreed)
- **Nodes are derived from the tabs, not drawn:** each tab is a box, its demand targets supply nodes (right), its inbound production need nodes (left). A demand added in a tab appears here.
- **Edges are the only new data:** `{from: {tab, item}, to: {tab, item}}`, kept in the book (039). Same item only.
- **Shapes allowed:** one to one, one to many, many to one. A link that would make a many-to-many group is refused, with a short note. If more complex chains are needed, that's for later.
- **Rates are derived, never edited:** one supply to many needs, each edge carries what its need asks for; many supplies to one need, each edge carries what its supply makes.
- **Highlights:** a supply node short when its edges take more than it makes, surplus when less; a need node short when its edges bring less than it asks for. Unconnected nodes stay neutral (final products, mined or outside inputs).
- **Nothing adjusts on its own:** changing a tab's numbers only changes the highlights; the user fixes the plans.
- **An edge means "routed in game":** drawing it records that the connection exists.
- **Leftovers:** a tab that gives a by-product to another sets it as a demand target (covered by the by-product, ticket 031, so no buildings are added); the other tab sets it as inbound production. Both then show as nodes and can be linked. No calculated results need storing: the chain tab works from demands and inbound production only, in the browser.
- Nodes movable, positions kept (as in the logistics editor, 036). Double-click a tab's box to open that tab.
- Deleting a tab removes its nodes and edges, with a notice; renaming keeps them (stable tab ids).

## Notes
- Logistics mode: an edge could later show the belts it needs, as the graph's edges do.
