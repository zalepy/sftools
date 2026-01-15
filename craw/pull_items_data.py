import json
import re
from typing import Dict

import requests


def grep_recipe(item_dict: dict, data: str) -> dict:
    name_n_building = re.findall(r'<h5 class="card-title">\s*?(\w.+?)\s*?</h5>[^~]+?<em><small>\([^\)]+?alt="(\w+?)"[^\)]+?>.+?</a>\)</small></em>', data)
    if not name_n_building:
        return item_dict

    recipe_name = name_n_building[0][0]
    recipe = {'building': name_n_building[0][1]}
    sub_datas = data.split('<div class="col-6">')
    ingredient_counter = 1
    column_flag = 'ingredient'
    for sub in sub_datas:
        ingredient_matches = re.findall(r'<div><span.+?><em><small>\(([^\)]+? / min)\)</small></em></span>([\d\.]+?).{1,3}<img src="[^"]+?" alt="([^"]+?)".+?>.+?</a></div>', sub)
        if not len(ingredient_matches):
            continue
        for match_item in ingredient_matches:
            match_rate = match_item[0]
            match_stack = match_item[1]
            match_name = match_item[2]


            # Helper to clean string
            def clean_str(val):
                val = re.sub(r'<[^>]+>', '', val)
                val = " ".join(val.split())
                val = val.replace(" MW", "").replace(" MJ", "").replace(" m", "")
                val = val.replace("\u00b3", "").replace("/ min", "")
                return val.strip()

            match_rate = clean_str(match_rate)
            match_stack = clean_str(match_stack)
            match_name = clean_str(match_name)

            recipe[column_flag + str(ingredient_counter) + '_rate'] = match_rate
            recipe[column_flag + str(ingredient_counter) + '_stack'] = match_stack
            recipe[column_flag + str(ingredient_counter) + '_name'] = match_name
            ingredient_counter += 1

        if column_flag == 'output':
            column_flag = 'error'
            ingredient_counter = 1
        if column_flag == 'ingredient':
            column_flag = 'output'
            ingredient_counter = 1

    existing_recipes = item_dict.get('recipes', {})
    existing_recipes[recipe_name] = recipe
    item_dict['recipes'] = existing_recipes

    return item_dict


def grep_recipes(item_dict: dict, data: str) -> dict:
    separator = '<h5 class="card-title">'
    recipe_sections = data.split(separator)
    for section in recipe_sections:
        item_dict = grep_recipe(item_dict, separator + section)

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


# =================================================================================================================================================
# =================================================================================================================================================
def main():
    url_base = 'https://satisfactory-calculator.com'
    
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=requests.adapters.Retry(total=5, backoff_factor=1))
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    print("Fetching items list...")
    raw_response = session.get(f'{url_base}/en/items?switchGameBranch=Experimental', timeout=30)

    item_matches = re.findall(r'<a href="(?P<link>[^"]+?)">\s+<strong>(?P<name>[\w\s]+?)</strong>', raw_response.text)
    items = []

    for item_match in item_matches:
        item_url_path = item_match[0]
        item_name = item_match[1]
        item_dict = {'name': item_name}
        print('>>> processing', item_name)
        # if item_name == 'Automated Wiring':
        # if item_name == 'Polymer Resin' or item_name == 'Plastic':
        # if item_name == 'Battery':
        try:
            raw_response = session.get(url_base + item_url_path, timeout=30)
            trimmed = raw_response.text.split('<h4>' + item_name + '</h4>')[-1]
            sections = parse_item_page_sections(trimmed)
            item_dict = parse_item_details(item_dict, sections['item'])
            if 'recipes' in sections.keys():
                item_dict = grep_recipes(item_dict, sections['recipes'])
            if 'alternatives' in sections.keys():
                item_dict = grep_recipes(item_dict, sections['alternatives'])

            items.append(item_dict)
        except Exception as e:
            print(f"Failed to process {item_name}: {e}")


    with open('data/items.json', 'w') as f:
        json.dump(items, f, indent=2)
    print(f"Successfully processed {len(items)} items.")


if __name__ == "__main__":
    main()


