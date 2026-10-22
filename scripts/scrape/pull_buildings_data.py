import json
from pathlib import Path
import re
from typing import Dict

import requests

from pull_items_data import grep_recipes

DATA_DIR = Path(__file__).resolve().parents[2] / 'src' / 'sftools' / 'data'


def grep_extraction_recipes(building_name: str, rest_data: str, items_list: list):
    # Split by the h5 items in "Used to craft" table
    parts = re.split(r'<h5 class="mb-0">(.+?)</h5>', rest_data)
    # parts[0] is garbage before first item
    # parts[1] is first item name
    # parts[2] is first item table content
    for i in range(1, len(parts), 2):
        item_name = parts[i].strip()
        item_content = parts[i+1]
        
        # Find the item in items_list
        target_item = next((item for item in items_list if item['name'] == item_name), None)
        if not target_item:
            continue
            
        # Find all rate/purity pairs
        # Matches: 30 / min (Impure) or 120m3 / min (Normal)
        rate_matches = re.findall(r'<em><small>\s*([\d\.,]+(?:m3|m\u00b3)?)\s*/\s*min\s*(?:\(\s*(.+?)\s*\))?\s*</small></em>', item_content, re.IGNORECASE | re.DOTALL)
        
        for rate, purity in rate_matches:
            # Clean rate (replace superscript 3 with 3, keep m3 if present)
            rate = rate.replace("\u00b3", "3")
            # If it contains m3, keep it. Otherwise, clean of units if any.
            if "m3" in rate:
                clean_rate = rate.replace(" ", "").strip()
            else:
                # Remove any leftover units like 'm' or space
                clean_rate = re.sub(r'[^\d\.,]', '', rate).strip()
            
            purity_str = purity.strip() if purity else ""
            recipe_name = f"{item_name} ({purity_str.lower()}) at {building_name}" if purity_str else f"{item_name} at {building_name}"
            
            recipe = {
                "building": building_name,
                "output1_rate": clean_rate,
                "output1_stack": "1",
                "output1_name": item_name
            }
            
            if 'recipes' not in target_item:
                target_item['recipes'] = {}
            target_item['recipes'][recipe_name] = recipe


def parse_item_details(item_dict: dict, data: str) -> Dict:
    detail_matches = re.findall(r'<span>\s+?<i class=".+?"></i> (.+?)\s+?</span>\s+?<span class="float-right"><strong>(.+?)</strong></span>', data)
    for dm in detail_matches:
        if dm[0] != 'Power planner':
            key = dm[0]
            val = dm[1]
            # Strip HTML tags
            val = re.sub(r'<[^>]+>', '', val)
            # Normalize whitespace
            val = " ".join(val.split())

            # Strip units
            val = val.replace(" MW", "").replace(" MJ", "")
            val = val.replace(" / min", "").replace("/ min", "")
            # Fix unicode units to m3
            val = val.replace("\u00b3", "3")
            val = val.replace(" m3", "m3").replace(" m", "")
            item_dict[key] = val

    return item_dict


def parse_item_page_sections(data: str) -> Dict[str, str]:
    rest = data
    sections = {}
    candidate_section = 'item'
    if rest.count('<strong>Recipes</strong>'):
        section_data, rest = rest.split('<strong>Recipes</strong>')
        sections[candidate_section] = section_data
        candidate_section = 'recipes'
    if rest.count('<strong>Alternate recipes</strong>'):
        section_data, rest = rest.split('<strong>Alternate recipes</strong>')
        sections[candidate_section] = section_data
        candidate_section = 'alternatives'
    if rest.count('Used to unlock'):
        section_data, rest = rest.split('<strong>Used to unlock</strong>')
    elif rest.count('<strong>Used to craft</strong>'):
        section_data, rest = rest.split('<strong>Used to craft</strong>')
    else:
        # If none of the above, just take a chunk as item and keep rest
        # But usually buildings have details at top.
        pass

    sections[candidate_section] = section_data
    sections['rest'] = rest
    return sections


# =================================================================================================================================================
def pull_buildings(items_list: list = None):
    url_base = 'https://satisfactory-calculator.com'
    
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=requests.adapters.Retry(total=5, backoff_factor=1))
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    raw_response = session.get(f'{url_base}/en/buildings', timeout=30)

    # Improved regex to catch buildings with or without <strong> tags
    item_matches = re.findall(r'<a href="(?P<link>/en/buildings/detail/id/[^"]+?)">(?:\s*<strong>)?\s*(?P<name>.+?)\s*(?:</strong>)?\s*</a>', raw_response.text)
    
    # Deduplicate by link and prioritize names without HTML
    seen_links = {}
    for link, name in item_matches:
        name = re.sub(r'<[^>]+>', '', name).strip()
        if link not in seen_links or (name and not seen_links[link]):
            seen_links[link] = name
            
    buildings = []

    for item_url_path, item_name in seen_links.items():
        building_dict = {'name': item_name}
        print('>>> processing', item_name)
        try:
            raw_response = session.get(url_base + item_url_path, timeout=30)
            trimmed = raw_response.text.split('<h4>' + item_name + '</h4>')[-1]
            sections = parse_item_page_sections(trimmed)
            building_dict = parse_item_details(building_dict, sections['item'])
            if 'recipes' in sections.keys():
                building_dict = grep_recipes(building_dict, sections['recipes'])
            if 'alternatives' in sections.keys():
                building_dict = grep_recipes(building_dict, sections['alternatives'])

            # Enrichment logic for extraction buildings
            if items_list is not None and building_dict.get('Category') in ['Extraction', 'Extractor']:
                grep_extraction_recipes(item_name, sections.get('rest', ''), items_list)

            buildings.append(building_dict)
        except Exception as e:
            print(f"Failed to process {item_name}: {e}")

    return buildings


def main():
    buildings = pull_buildings()
    with open(DATA_DIR / 'buildings.json', 'w') as f:
        json.dump(buildings, f, indent=2)
    print(f"Successfully processed {len(buildings)} buildings.")


if __name__ == "__main__":
    main()


