# 014 — Recipe model: lists instead of ingredient1..4 / output1..2

**Type:** refactor · **Priority:** P3 · **Depends on:** 004 · **Status:** Open

- [ ] `Recipe(name, building, product: (Item, rate), byproducts: list[(Item, rate)], ingredients: list[(Item, rate)], type)`, using dataclasses
- [ ] Simplify the loader, `generate_demands`, `generate_production_node`, `update_from_recipe` and `__repr__` (about 150 lines less)
- [ ] Remove `ProductionNode.absorb_node` and `__add__` (that logic now lives in `FactoryGraph`), and `Demand.__add__` if unused
- [ ] Remove the long "thinking out loud" comments in `recalculate` and `get_ui_data`
