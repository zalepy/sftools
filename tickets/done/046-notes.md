# 046 — Notes per node and per plan

**Type:** feature · **Priority:** P3 · **Status:** Done · **Related:** [037](037-built-marks.md), [038](038-node-tab.md), [039](039-plan-tabs.md), [045](045-move-branch-to-inbound.md)

## Goal
Free-text notes in the Planner: one per node (e.g. where it's built, what's left to do) and one for the whole plan. Notes are saved with the plan, so they go into book and plan exports.

## Decisions (agreed with the user, 2026-10-20)
- **Node note:** a textarea with its own Save button on the Node tab. It's on production and inbound nodes, but not on the Sink or the logistics (zoomed-in) nodes. Demand targets were meant to have one too, but a demand circle can't be selected (clicking it selects the node making it), so it has none.
- **Plan note:** a textarea with its own Save button on the Planner tab, under the demand/inbound rows.
- **Plain text,** with no length limit.
- **Save button,** not save-as-you-type. If you select another node, switch tabs, etc. with an unsaved edit, the app asks "Discard unsaved note?".
- **Storage:** in the plan snapshot, like built marks (`state.built`), keyed by node id: `notes: {node_id: text}` plus the plan note. This brings undo/redo, the tab, and book and plan export with it. Saving a note records an undo step.
- **Node ids are path-based** (`<parent id>__<item>`), so a note stays with its node when the node's recipe changes.
- **Recipe-change line:** when a node that already has a note switches recipe, a line `dd.mm.yy: recipe changed from X to Y` is appended to the note right away, as part of the same change (no Save needed). A node without a note gets none.
- **Node gone from the plan:** its note is deleted. Undo brings it back.
- **Merged nodes:** a merged node uses one path's id. If a plan edit changes which path, the note is deleted with the old id. Built marks have the same limit, which is accepted.
- **Move Branch (045):** the moved nodes leave the source plan, so their notes are deleted there (undo restores them). Nothing is copied to the destination.
- **Hover tooltip:**
  - Hold the mouse still over a node with a note for a moment (~0.6 s). The note shows in the Legend's place, covering it while the mouse stays on the node. Moving off hides it.
  - Selecting a node keeps its note shown there until the node is deselected (or another node is selected, which shows that node's note, if it has one).
  - Nodes without a note show nothing.
- **No marker on the graph** for nodes with notes: the graph is busy enough.
- **Out of scope:** Chain tab notes (per Chain node and for the Chain itself). A separate pass can add them if really needed.

## Notes
- Implemented 2026-10-20. Notes live in the plan snapshot (`notes`, `planNote`). The "Discard unsaved note?" question comes when selecting another node, edge or logistics node, switching plan tabs, or undo/redo. New Plan and loading a book drop the drafts with their own confirmation.
- Besides selecting another node, a click on the empty graph also hides the pinned note. The box also hides when the mouse leaves the graph.
- The dated line is added by a recipe switch on the node and by preferred-recipe changes that switch it, but not by undo/redo or tab switches.
- Tests: `tests/integration/test_notes.py`.
