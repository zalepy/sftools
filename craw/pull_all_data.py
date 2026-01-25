import json
import os
from pull_items_data import pull_items
from pull_buildings_data import pull_buildings

def main():
    print("Starting full data pull...")
    
    # 1. Pull items first
    print("Step 1: Pulling items data...")
    items = pull_items()
    
    # 2. Pull buildings and enrich items
    print("Step 2: Pulling buildings data and enriching items...")
    # pull_buildings(items) will modify the items list in-place
    buildings = pull_buildings(items)
    
    # 3. Save both
    print("Step 3: Saving data...")
    os.makedirs('data', exist_ok=True)
    
    with open('data/items.json', 'w') as f:
        json.dump(items, f, indent=2)
    print(f"Saved {len(items)} items to data/items.json")
    
    with open('data/buildings.json', 'w') as f:
        json.dump(buildings, f, indent=2)
    print(f"Saved {len(buildings)} buildings to data/buildings.json")
    
    print("Done!")

if __name__ == "__main__":
    main()
