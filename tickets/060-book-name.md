# 060 — Name the book; New Book; warn before losing unsaved changes

**Type:** feature · **Priority:** P2 · **Status:** Open · **Related:** [039](done/039-plan-tabs.md), [040](done/040-chain-tab.md)

## Goal
Keep several books as files and switch between them without confusion. Example: the RAD production (uranium to ficsonium) moves out of the main book into a book of its own, split into tabs there. Today a book has no name: every Save Book is `sf_planner_book.json`, and loading a book replaces the tabs with a confirm that names neither book. Discussed 2026-11-02.

Several books kept in the browser, with a switcher, are left out: the files are what the user keeps, and a second copy in localStorage is one more thing to drift.

## Name
- The book has a **name**, saved in the book (`name`, next to `tabs`, `active`, `chain`) in localStorage and in the file. A book without one (saved before this) is shown as "Book".
- Shown at the start of the tab strip; double-click renames, as for a tab.
- **Save Book** names the file after it: `sf_planner_<name>.json`, made safe as `fileName` does today. Without a name: `sf_planner_book.json`, as now.
- **Load a book** takes its name from the file's `name`. A file without one gets the file's name without `sf_planner_` and `.json` (so today's `sf_planner_book.json` gives "book").
- Each mode (simple, logistics) has its own book, so its own name.

## Unsaved changes
- The book remembers whether it changed since its last Save Book or load (a flag in the saved book, so a reload keeps it). Any change to a tab, a tab's name, the tabs' order, the chain, or the book's name counts. Export Plan doesn't clear it (it saves one tab).
- While changed, the name shows a mark (`Main •`), with a title saying it isn't saved.
- **Loading a book** asks only when the current book has unsaved changes: "'Main' has unsaved changes. Load 'RAD' (4 tabs) in place of its 17 tabs?" Without changes, it loads without asking (Undo doesn't cover a load, but nothing is lost: the file is there).
- Importing a single plan adds a tab, as today; it marks the book changed.

## New Book
- A **New Book** button, next to Save Book: asks for a name, and replaces the tabs with one empty tab and an empty chain. Asks first when the current book has unsaved changes, as for loading. Preferred recipes and colors stay (they're this browser's, as on load of a book without them).
- New Plan stays as it is: it clears the shown tab.

## Moving a part of a book into a new one (no code; for the user guide)
Export Plan on the tab, New Book, Import the plan, split it into tabs there (Move branch, 045), Save Book; then load the main book and close that tab. Splits that keep a by-product inside one tab (e.g. the waste burned where it's used, with Fuel Rods passed between tabs) need nothing more; a by-product as a Chain supply between tabs is not part of this.

## Tests
- Integration: rename the book, Save Book downloads `sf_planner_<name>.json` with the name inside; loading a book file brings its name; a file without one takes it from the file name.
- The mark appears after a change and goes after Save Book; it survives a reload.
- Loading a book asks only with unsaved changes; New Book likewise, and leaves one empty tab and the preferred recipes and colors.
- Unit (`tests/js/`): the name from a file name, and the confirm text, in a pure module.
- The user guide: the book's name, New Book, and the steps above.
