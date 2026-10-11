# 012 — Recipe switches are not saved

**Type:** bug · **Priority:** P1 · **Related:** 007, 010 · **Status:** Done

> **Update (2026-10-11):** `recipes` is part of the plan (localStorage, export/import, `/api/calculate`) and is applied parents first. Covered by `test_recipe_switch_is_replayed`.

## Problem
`FactoryGraph.recipe_overrides` is declared but never used. `/api/calculate` doesn't accept recipe switches, so after a reload or recalculation they are lost. Merges or overrides that referenced nodes from the switched subtree then silently fail to apply.

## Fix
- [ ] Add `recipes: {node_id: recipe_name}` to the plan state: client localStorage, `CalculateRequest`, export/import
- [ ] Apply recipe switches in a fixed order (parents first) before merges and overrides
- [ ] Round-trip test: build → switch → merge → override → serialize → rebuild gives an identical graph
