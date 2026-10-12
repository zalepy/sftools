# 019 — Gaps in the scraped game data

**Type:** data · **Priority:** P2 · **Related:** 013 · **Status:** Done

> **Update (2026-10-11):** Fixed in the scraper (`scripts/scrape/pull_items_data.py`) and re-scraped:
> - Recipe headers matched only single-word building names (`alt="(\w+?)"`), so Particle Accelerator, Quantum Encoder and Nuclear Power Plant recipes were dropped. That's 27 recipes, including base Diamonds.
> - The ingredient/output columns are now taken by position, so Excited Photonic Matter (no ingredients) gets its output.
> - Items that recipes use but the items list doesn't include (creature `* Remains`, under `/tools/`) are now fetched too.
> - Zero-rate placeholder recipes are skipped (a 0 m³/min "Nitrogen Gas" at the Resource Well Extractor that lists itself as input).
> - Same-name recipes are kept apart: *Turbo Rifle Ammo (Manufacturer)* next to the Blender one.
> - Stack counts were cut to one digit (`20x` → 2); fixed.
> - The buildings scraper reuses the item recipe parser instead of keeping its own copy.
> - Per-recipe power: `Building.power_for(recipe)` uses the midpoint of the listed range (Diamonds 250–750 → 500 MW). This replaces the hard-coded −1500 MW for the whole Particle Accelerator.
> - **Uranium Ore (Bauxite)** at 480 Bauxite/min is correct (48 per 6 s on the site).
> - The tests no longer allow exceptions; the only items without a recipe are world items (`ITEMS_WITHOUT_RECIPES`).
>
> Left over: the buildings scraper still fails on non-production buildings (Radar Tower, generators, The HUB, …) because their pages have no recipe sections. That isn't needed by the planner, so it's not tracked.

Found while writing the data validation tests (013). The tests list the known exceptions in `RECIPES_WITHOUT_OUTPUT` and `UNKNOWN_INGREDIENTS` (`tests/unit/test_game_data.py`); remove them once each one is fixed.

## Missing recipes
- **Particle Accelerator and Quantum Encoder recipes are missing.** These items have no recipe at all: Diamonds (base recipe), Plutonium Pellet, Nuclear Pasta, Dark Matter Crystal, Ficsonium, Ficsonium Fuel Rod, Superposition Oscillator, Neural-Quantum Processor, AI Expansion Server, Alien Power Matrix.
  - `buildings.json` *does* list their per-recipe power (`Power used (Diamonds)` etc.), so the scraper sees the buildings but not their recipes.
  - Because of this gap, Diamonds currently defaults to *Alternate: Pink Diamonds*.
- Items with no recipe because they really have none (gathered, or by-products of power generation): Leaves, Wood, Mycelia, Flower Petals, power slugs, FICSIT Coupon, Uranium/Plutonium Waste, Color Cartridge, Beacon. Nothing to do; just don't flag these.

## Malformed recipes
- **Excited Photonic Matter**: the Converter recipe lists `200m3` Excited Photonic Matter as an *ingredient* and has no output. In the game, the Converter makes it from nothing.
- **Alien protein recipes** (Hatcher/Hog/Spitter/Stinger Protein) use `* Remains` ingredients, which aren't in `items.json`. The loader drops those ingredients.
- **Uranium Ore (Bauxite)** lists 480 Bauxite/min as input. Compare with the other Converter ore recipes (about 100–120/min); this looks like a scraping or units error.

## Power
- Buildings with power that depends on the recipe (Particle Accelerator, Quantum Encoder, Converter) get 0 MW. The exception is a hard-coded −1500 MW applied to the whole Particle Accelerator.
- Power should be stored per recipe, using the average of the range given (e.g. `250 - 750` → 500).

## Tasks
- [ ] Scrape Particle Accelerator and Quantum Encoder recipes
- [ ] Fix the Excited Photonic Matter output and add the creature `* Remains` items
- [ ] Check the Uranium Ore (Bauxite) rates
- [ ] Per-recipe power for variable-power buildings
- [ ] Run `tests/unit/test_game_data.py` against fresh scraper output before committing it
