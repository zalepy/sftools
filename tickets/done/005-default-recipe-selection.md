# 005 — Default recipe can belong to a different item

**Type:** bug · **Priority:** P0 · **Related:** 004 · **Status:** Done

> **Update (2026-10-11):** `default_recipe_for(item)` in `engine/calculator.py`. Preference order: no unpackaging → main product → basic, converter, alternate → recipe named after the item → data order. Alternates are used when no basic recipe makes the item as main product, because by-product defaults loop (Compacted Coal ← Ionized Fuel ← Rocket Fuel ← Turbofuel ← Compacted Coal). Expansion also stops if an item reappears in its own chain.

## Problem
`calculate_demands` and `expand_new_subtree` pick "the first BASIC recipe in `item.recipes`". For some items, that is a recipe where the item is only a by-product or ingredient:
Silica → *Alumina Solution*, Water → *Aluminum Scrap*, Heavy Oil Residue → *Plastic*, Polymer Resin → *Fuel*, Sulfuric Acid → *Encased Uranium Cell*, Crude Oil → *Unpackage Oil*.

## Fix
- [ ] Only consider recipes whose product (from 004) is the item
- [ ] Choose a deterministic default: the standard game recipe first, then a non-packaging recipe, then extraction for raw resources
- [ ] Put the selection in one helper, `default_recipe_for(item)`, used by both code paths

## Acceptance criteria
- For every item that has recipes, `default_recipe_for(item).product is item`
