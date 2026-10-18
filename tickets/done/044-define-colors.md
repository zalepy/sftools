# 044 — Define item colors

**Type:** feature · **Priority:** P3 · **Status:** Done · **Related:** [043](done/043-preferred-recipes.md)

## Problem
The Colors tab only listed the built-in colors (`node_colors.json`, 22 items). Any other item stayed the default slate, with no way to give it a color.

## Decision
- **Define** row at the bottom of the Colors tab: an item (autocomplete from all items), a color, and Define. The item joins the list; one already there gets the new color.
- **×** on each row: on a built-in item it puts the built-in color back; on an item the user defined it removes the row.
- **Save Colors stays**: edits, defined items and removals take effect when saved, as before. Saving now also recolors the plan shown.
- No color swatch on the Node tab (considered, not wanted).

## Done (2026-10-18)
- `index.html`: the Define row (`#color-add-item`, `#color-add-value`, `#color-add-btn`) and an error line for an unknown item.
- `panel.js`: `renderColorList(colors)` renders unsaved edits too, with × per row; `initColorDefine()`. `state.defaultColors` holds the built-in colors.
- The saved map (`sf_planner_colors`) is still the whole list, so a removed item is gone after Save; books carry it as before.
- Browser test: `test_defining_colors`.
