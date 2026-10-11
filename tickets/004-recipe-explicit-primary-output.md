# 004 — Recipe product guessed from the recipe name

**Type:** bug · **Priority:** P0 · **Status:** Open

## Problem
`Recipe.output_item`, `output_rate`, `sink_item` and `sink_rate` decide which output is the product by checking whether the recipe name contains the item name.
- 38/100 alternate recipes (Bolted/Stitched/Adhered Iron Plate, Steel Rod, Iron Alloy Ingot, …) fall through to output2, which is `None`.
- Switching to one of them crashes with `TypeError: '>' not supported between NoneType and int` in `FactoryGraph.recalculate`.
- `generate_production_node` always uses `output1_rate`, while `update_from_recipe` uses `output_rate`. This is wrong for the 5 recipes whose product is output2 (Unpackage Oil, Instant Scrap, Quartz Purification, Fertile Uranium, Dark-Ion Fuel).

## Fix
- [ ] When loading, record the item whose `recipes` list the recipe came from. That item is the product; store it as `Recipe.product` / `product_rate` and treat the other output as the by-product.
- [ ] Use the same source in `generate_production_node` and `update_from_recipe`
- [ ] Check the case where a recipe appears under several items (by-product listings)

## Acceptance criteria
- Every recipe has a non-null product and product rate
- Switching to any alternate recipe works without errors
