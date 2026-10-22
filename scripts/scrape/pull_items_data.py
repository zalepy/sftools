import json
from pathlib import Path
import re
from typing import Dict

import requests

DATA_DIR = Path(__file__).resolve().parents[2] / 'src' / 'sftools' / 'data'


RECIPE_HEADER = re.compile(
    r'<h5 class="card-title">\s*?(\w.+?)\s*?</h5>[^~]+?<em><small>\([^\)]+?alt="([^"]+?)"[^\)]+?>.+?</a>\)</small></em>')
RECIPE_ENTRY = re.compile(
    r'<div><span.+?><em><small>\(([^\)]+? / min)\)</small></em></span>([\d\.]+)[^<\d]{1,3}'
    r'<img src="[^"]+?" alt="([^"]+?)"[^>]*>\s*<a href="([^"]+?)">.+?</a></div>')


def clean_str(val):
    val = re.sub(r'<[^>]+>', '', val)
    val = " ".join(val.split())
    val = val.replace(" MW", "").replace(" MJ", "")
    val = val.replace("³", "3")
    val = val.replace(" / min", "").replace("/ min", "").replace("/min", "")
    val = val.replace(" m3", "m3")
    val = val.replace(" m", "")
    return val.strip()


def grep_recipe(item_dict: dict, data: str, links: Dict[str, str] = None) -> dict:
    """
    Parses one recipe card. The card body has two columns, ingredients then outputs; either can be
    empty (e.g. the Converter makes Excited Photonic Matter from nothing), so columns are taken by position.
    `links` collects name -> page path for every item the recipe refers to.
    """
    name_n_building = RECIPE_HEADER.findall(data)
    if not name_n_building:
        return item_dict

    recipe_name = name_n_building[0][0]
    recipe = {'building': name_n_building[0][1]}
    # [0] is the card header, [1] ingredients, [2] outputs; anything after belongs to the next card
    columns = data.split('<div class="col-6">')[1:3]
    for column_flag, column in zip(('ingredient', 'output'), columns, strict=False):  # a card may lack its outputs column
        for counter, (rate, stack, name, href) in enumerate(RECIPE_ENTRY.findall(column), start=1):
            name = clean_str(name)
            recipe[f'{column_flag}{counter}_rate'] = clean_str(rate)
            recipe[f'{column_flag}{counter}_stack'] = clean_str(stack)
            recipe[f'{column_flag}{counter}_name'] = name
            if links is not None:
                links.setdefault(name, href)

    # Placeholders such as "Nitrogen Gas" at a Resource Well Extractor have 0 / min output
    output_rates = [v for k, v in recipe.items() if k.startswith('output') and k.endswith('_rate')]
    if not output_rates or all(re.fullmatch(r'0(\.0+)?(m3)?', rate) for rate in output_rates):
        return item_dict

    existing_recipes = item_dict.get('recipes', {})
    # The site has a few distinct recipes with the same name (e.g. Turbo Rifle Ammo in a Blender
    # and in a Manufacturer); keep both by naming the later one after its building
    existing = existing_recipes.get(recipe_name)
    if existing is not None and existing.get('building') != recipe['building']:
        recipe_name = f"{recipe_name} ({recipe['building']})"
    existing_recipes[recipe_name] = recipe
    item_dict['recipes'] = existing_recipes

    return item_dict


def grep_recipes(item_dict: dict, data: str, links: Dict[str, str] = None) -> dict:
    separator = '<h5 class="card-title">'
    recipe_sections = data.split(separator)
    for section in recipe_sections:
        item_dict = grep_recipe(item_dict, separator + section, links)

    return item_dict


def parse_item_details(item_dict: dict, data: str) -> Dict:
    detail_matches = re.findall(r'<span>\s+?<i class=".+?"></i> (.+?)\s+?</span>\s+?<span class="float-right"><strong>(.+?)</strong></span>', data)
    for dm in detail_matches:
        key = dm[0]
        val = dm[1]
        # Strip HTML tags
        val = re.sub(r'<[^>]+>', '', val)
        # Normalize whitespace
        val = " ".join(val.split())

        # Strip units
        val = val.replace(" MW", "").replace(" m", "").replace(" MJ", "")
        # Fix unicode units
        val = val.replace("\u00b3", "").replace("/ min", "")
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
        section_data = rest

    sections[candidate_section] = section_data
    sections['rest'] = rest
    return sections


def pull_item(session, url_base: str, item_url_path: str, item_name: str, links: Dict[str, str]):
    print('>>> processing', item_name)
    try:
        raw_response = session.get(url_base + item_url_path, timeout=30)
        trimmed = raw_response.text.split('<h4>' + item_name + '</h4>')[-1]
        sections = parse_item_page_sections(trimmed)
        item_dict = parse_item_details({'name': item_name}, sections['item'])
        if 'recipes' in sections.keys():
            item_dict = grep_recipes(item_dict, sections['recipes'], links)
        if 'alternatives' in sections.keys():
            item_dict = grep_recipes(item_dict, sections['alternatives'], links)
        return item_dict
    except Exception as e:
        print(f"Failed to process {item_name}: {e}")
        return None


# =================================================================================================================================================
def pull_items():
    url_base = 'https://satisfactory-calculator.com'
    
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=requests.adapters.Retry(total=5, backoff_factor=1))
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    print("Fetching items list...")
    raw_response = session.get(f'{url_base}/en/items?switchGameBranch=Experimental', timeout=30)

    item_matches = re.findall(r'<a href="(?P<link>[^"]+?)">\s+<strong>(?P<name>[\w\s\-\:]+?)</strong>', raw_response.text)
    items = []
    links: Dict[str, str] = {}  # every item referenced by a recipe -> its page

    for item_url_path, item_name in item_matches:
        item = pull_item(session, url_base, item_url_path, item_name, links)
        if item:
            items.append(item)

    # Recipes can use items that are not in the items list (e.g. creature remains are under /tools/)
    known = {item['name'] for item in items}
    for item_name, item_url_path in sorted(links.items()):
        if item_name not in known:
            item = pull_item(session, url_base, item_url_path, item_name, links)
            if item:
                items.append(item)

    return items


def main():
    items = pull_items()
    with open(DATA_DIR / 'items.json', 'w') as f:
        json.dump(items, f, indent=2)
    print(f"Successfully processed {len(items)} items.")


if __name__ == "__main__":
    main()


