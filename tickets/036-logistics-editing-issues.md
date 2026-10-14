# 036 — Splitter/merger editing problems (logistics mode)

**Type:** bug · **Priority:** P2 · **Status:** Open (needs description) · **Related:** [033](done/033-logistics-mode.md), [034](034-balancers.md)

## Problem
Editing splitters and mergers in a zoomed-in logistics node doesn't work as it should. Reported 2026-10-14; the user is testing further to describe what exactly fails.

## Open questions
- Which actions fail: adding a splitter or merger, laying belts to or from it, deleting it, the overflow toggle, or Reset?
- What happens instead: the belt is refused (with what notice), nothing happens, the layout resets, or the flows or warnings are wrong?
- Steps to reproduce, ideally with an exported plan (`sf_logistics_save.json`) and the logistics node (`<node> | in/out`).
