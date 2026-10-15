# 036 — Splitter/merger editing problems (logistics mode)

**Type:** bug · **Priority:** P2 · **Status:** Done · **Related:** [033](done/033-logistics-mode.md), [034](034-balancers.md)

> **Done (2026-10-15).** What was wrong, and what changed:
> - **Placement:** the zoomed-in view used a plain dagre layout, so nodes landed anywhere and a new part, with no belts, went to a corner. Now sources (buildings out, entries in) are a column on the left, sinks on the right, and parts in columns between by belt order, at the height of what they connect to; new parts go under the others in the first middle column.
> - **Moving nodes and selecting parts:** every press on a node started laying a belt (nodes weren't grabbable), which also swallowed the click that selects a node, so a new part couldn't be selected or deleted. Now dragging a node moves it, and positions are kept in the plan (`logistics.positions`, browser only) once a node is moved or the side edited, so edits don't rearrange it. A click selects.
> - **Laying belts:** from the dots under a node, one per free output port (user's choice: handles, at the bottom). While dragging, nodes that can take the belt turn green and the others fade, so the port limits show before the drop.
> - **Moving belts:** a selected belt shows a handle at each end; drag one to another node.
> - **Splitter to an exit refused:** an exit took only as many belts as its edge needs at the highest tier (usually 1), and it already had one. Exits now have a merger built in, taking up to 3 belts per line ("Exit Merger"), and entries a splitter, splitting each line into up to 3. The suggested output layout uses them, so it needs no separate mergers for up to 3 buildings per exit; `complexity` counts the built-in ones that are used.
> - **Shapes:** mergers are squares, splitters stay rhombuses.
> - **Slow edits (3+ s):** each edit is a request to the server, which recalculates the plan; on UAT (Render's free plan) that can take seconds. Not changed.
>
> Tests: `test_editing_a_logistics_node` (drag from a dot, click to select, move a belt's end, the full exit refused, move a node, Reset), `test_an_exit_merges_up_to_three_belts_per_line`.

## Problem
Editing splitters and mergers in a zoomed-in logistics node doesn't work as it should. Reported 2026-10-14; the user's notes (2026-10-15) are below.

## Open questions
- Which actions fail: adding a splitter or merger, laying belts to or from it, deleting it, the overflow toggle, or Reset?
  = initial placement of the nodes is unordered. I'd expect the prod ones to be a column on the left, and the exit nodes to form a col on the right. This should leave all the middle space for the Merger/Splitter nodes.
  = cannot move nodes around. neither prod, neither the merger/splitter, neither the exit ones;
  = added splitter via button and it showed in the corner. I cannot delete it. I cannot select it.
  = annimations for drawing edge from the new node, show, but nothing seems to be a valid target, so I cannot place it. Actually added merger, and now it's valid. Deleting eges seems to work. I think adding edges also works, but has quirks. At least on one attempt it was quite slow 3+ sec; Conditions apply aka Splitters can have up to 3 outgoig edges, Ms can have up to 3 inbound edges. That's fine, but it's not clearly telegraphed
  = moving edges does not work - you need to delete (suffer rearangement) and draw as new
  = I couldn't place an edge from splitter to exit node. It only had 2 existing outgoing, so 3rd is available. I was able to link it to a merger, but no to the exit node;
- What happens instead: the belt is refused (with what notice), nothing happens, the layout resets, or the flows or warnings are wrong?
- Steps to reproduce, ideally with an exported plan (`sf_logistics_save.json`) and the logistics node (`<node> | in/out`).
