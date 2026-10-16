# 039 — Plan tabs and Save Book

**Type:** feature · **Priority:** P2 · **Status:** Open · **Related:** [040](040-chain-tab.md)

## Goal
Several plans side by side, as tabs, like the sheets of the spreadsheet the user worked from, and a single file holding all of them (a "book"). Discussed 2026-10-16.

## Tasks
- **Tabs:** a tab strip above the graph: add, rename (double-click), duplicate (for what-if variants), close. Each mode (simple, logistics) has its own set of tabs.
- **Storage:** each mode's localStorage key holds a book instead of one plan: `{tabs: [{id, name, plan}], active}`. Tabs have stable ids, so renaming doesn't break links (040). The current saved plan becomes the first tab, so nothing is lost. Colors and logistics settings stay shared, as today.
- **Undo:** a history per tab; switching tabs doesn't mix them.
- **New Plan** works on the active tab (or becomes "new tab"; decide while building).
- **Save Book / Load Book:** export all the tabs (and the chain tab's links, 040) as one JSON file; loading it replaces the book, with undo or a confirmation. **Export / Import** of a single plan stay as today, so older files still load; an imported plan opens in a new tab.
- The server doesn't change: it is stateless and calculates the active tab only.

## Notes
- localStorage limits (~5 MB) leave room for many plans.
- Tests: switching tabs keeps each plan and its undo; old saved plans migrate into a first tab; a book round-trips through Save/Load Book.
