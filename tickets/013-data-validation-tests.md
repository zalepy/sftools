# 013 — Validation tests against the real game data

**Type:** test · **Priority:** P1 · **Status:** Open

The current tests only check graph mechanics on hand-built data, which is why 003–005 went unnoticed.

- [ ] Load the real JSON once (session fixture) and check:
  - every recipe has a building, a product, and a product rate > 0
  - all rates are within sane bounds (fluids ≤ 600 m³/min per building)
  - every ingredient refers to a known item
  - `default_recipe_for(item).product is item` for every item that has recipes
- [ ] Golden test: a known chain (e.g. 2/min Smart Plating) gives the expected building counts
- [ ] Run the scraper's output through the same validation, so a bad scrape fails before it's committed
