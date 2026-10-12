# Satisfactory Data Scrapers

This folder contains Python scripts to scrape item and building data from [Satisfactory-Calculator](https://satisfactory-calculator.com).

## Usage

The main entry point is `pull_all_data.py`. Running this script will:
1. Fetch all items (raw resources, products, etc.)
2. Fetch all buildings.
3. **Enrich** raw resources with extraction recipes (e.g., Miner and Water Extractor outputs).
   Items that recipes use but the items list doesn't include (e.g. creature remains under `/tools/`) are fetched as well.
4. Save the results to `src/sftools/data/items.json` and `src/sftools/data/buildings.json`.

```bash
uv run --group scrape python scripts/scrape/pull_all_data.py
```

## Individual Scripts

- **pull_items_data.py**: Handles fetching and parsing of items. Can be run standalone to update only items, but won't include extraction recipes for raw resources.
- **pull_buildings_data.py**: Handles fetching and parsing of buildings. Includes logic to enrich an items list with extraction data if called programmatically.

## Data Enrichment Details

The scrapers are designed to handle the distinction between "Products" (which have recipes on their own page) and "Raw Resources" (which don't).
- **Miner Recipes**: Parsed from Miner building pages. Includes all purity levels (Impure, Normal, Pure).
- **Liquid Resources**: Parsed from Water Extractor, Oil Extractor, etc.
- **Recipe columns**: each recipe card has an ingredients column and an outputs column, taken by position (either may be empty).
- **Skipped**: placeholder recipes with a 0 / min output.
- **Duplicate names**: when two different recipes share a name, the later one gets its building appended, e.g. `Turbo Rifle Ammo (Manufacturer)`.
- **Recipe Naming**: To avoid name collisions across different miner tiers, extraction recipes are named using the pattern: `[Item] ([Purity]) at [Building]`. 
  - Example: `Iron Ore (pure) at Miner Mk.1`.
- **Unit Handling**: Superscript characters like `³` are normalized to `3` (e.g., `120m3`). The app loader reads only the leading number, so `120m3` is 120.

After scraping, run `uv run pytest tests/unit/test_game_data.py` before committing the new data.
