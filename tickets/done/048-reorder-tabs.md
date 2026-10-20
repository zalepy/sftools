# 048 — Reorder plan tabs by drag and drop

**Type:** feature · **Priority:** P3 · **Status:** Done · **Related:** [039](039-plan-tabs.md)

## Goal
Drag a plan tab in the strip above the graph to move it.

## Decisions (agreed with the user, 2026-10-20)
- **Native drag and drop:** mouse only. Touch is not supported.
- **No keyboard alternative.**
- **The order is `book.tabs`:** saved in the browser and in Save Book. The Chain tab refers to tabs by id, so it's unaffected. A reorder isn't an undo step (undo is per plan).

## Notes
- Implemented 2026-10-20 in `tabs.js` (`initDrag`, `moveTab`).
- A bar on the left or right edge of the tab under the pointer marks where the dragged tab lands; the dragged tab is faded while it moves.
- Near either end of the strip, a drag scrolls it.
- A tab being renamed can't be dragged, so the text in its name field can still be selected with the mouse.
- Test: `test_tabs_reorder_by_drag_and_drop` in `tests/integration/test_tabs.py`.
