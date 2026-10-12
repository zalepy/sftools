# 014 — Recipe model: lists instead of ingredient1..4 / output1..2

**Type:** refactor · **Priority:** P3 · **Depends on:** 004 · **Status:** Done

> **Done (2026-10-12).** `Recipe` is a dataclass with `product`, `byproducts` and `ingredients` as `(Item, rate)` lists. The unused `*_stack` values are no longer kept. The method that listed the outputs other than a node's item is now `other_outputs(item)`, since `byproducts` is the field. The removed code had no callers apart from one unit test of `ProductionNode.__add__`, which was dropped. Also removed: the unused `update_building_scale` and `clear_user_scale`. API responses for every craftable item and several mixed plans (merges, switches, overrides, splits) are byte-identical before and after, as is every recipe's `repr`.

- [x] `Recipe(name, building, product: (Item, rate), byproducts: list[(Item, rate)], ingredients: list[(Item, rate)], type)`, using dataclasses
- [x] Simplify the loader, `generate_demands`, `generate_production_node`, `update_from_recipe` and `__repr__` (about 150 lines less)
- [x] Remove `ProductionNode.absorb_node` and `__add__` (that logic now lives in `FactoryGraph`), and `Demand.__add__` if unused
- [x] Remove the long "thinking out loud" comments in `recalculate` and `get_ui_data`
