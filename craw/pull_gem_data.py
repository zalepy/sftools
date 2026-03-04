import json
import re
import os
import requests
from typing import List, Dict

def find_matching_closing_tag(html: str, start_index: int, tag_name: str) -> int:
    """
    Finds the matching closing tag for a given start tag index.
    Robust for nested tags of the same name.
    """
    # Find the end of the opening tag
    idx = html.find('>', start_index) + 1
    depth = 1
    
    open_pattern = f'<{tag_name}'
    close_pattern = f'</{tag_name}>'
    
    while depth > 0 and idx < len(html):
        next_open = html.find(open_pattern, idx)
        next_close = html.find(close_pattern, idx)
        
        if next_close == -1:
            return len(html) # Fallback to end of string if no matching close tag
            
        if next_open != -1 and next_open < next_close:
            depth += 1
            idx = next_open + len(open_pattern)
        else:
            depth -= 1
            idx = next_close + len(close_pattern)
            
    return idx

def pull_gems() -> List[Dict]:
    """
    Scrapes PoE skill gem data from the wiki proxy.
    """
    # List of skill gem names as requested, plus some common ones
    gem_names = [
                'Alchemists_Mark',
        'Ambush',
        'Anger',
        'Arc',
        'Arc_of_Oscillating',
        'Arc_of_Surging',
        'Arcane_Cloak',
        'Arcane_Surge_Support',
        'Arcanist_Brand',
        'Archmage_Support',
        'Arctic_Armour',
        'Armageddon_Brand',
        'Armageddon_Brand_of_Recall',
        'Armageddon_Brand_of_Volatility',
        'Assassins_Mark',
        'Automation',
        'Ball_Lightning',
        'Ball_Lightning_of_Orbiting',
        'Ball_Lightning_of_Static',
        'Bane',
        'Bane_of_Condemnation',
        'Bear_Trap',
        'Bear_Trap_of_Skewers',
        'Berserk',
        'Blade_Blast',
        'Blade_Blast_of_Dagger_Detonation',
        'Blade_Blast_of_Unloading',
        'Blade_Vortex',
        'Blade_Vortex_of_the_Scythe',
        'Bladefall',
        'Bladefall_of_Impaling',
        'Bladefall_of_Trarthus',
        'Bladefall_of_Volleys',
        'Blazing_Salvo',
        'Blight',
        'Blight_of_Atrophy',
        'Blight_of_Contagion',
        'Blood_and_Sand',
        'Blood_Rage',
        'Bodyswap',
        'Brand_Recall',
        'Cast_On_Critical_Strike_Support',
        'Cast_on_Death_Support',
        'Cast_on_Melee_Kill_Support',
        'Cast_when_Damage_Taken_Support',
        'Cast_when_Stunned_Support',
        'Cast_while_Channelling_Support',
        'Clarity',
        'Cold_Snap',
        'Cold_Snap_of_Power',
        'Conductivity',
        'Contagion',
        'Contagion_of_Subsiding',
        'Contagion_of_Transference',
        'Controlled_Destruction_Support',
        'Conversion_Trap',
        'Corrupting_Fever',
        'Crackling_Lance',
        'Crackling_Lance_of_Branching',
        'Crackling_Lance_of_Disintegration',
        'Creeping_Frost',
        'Creeping_Frost_of_Floes',
        'Cremation',
        'Cremation_of_Exhuming',
        'Cremation_of_the_Volcano',
        'Dark_Pact_of_Trarthus',
        'Dash',
        'Decoy_Totem',
        'Defiance_Banner',
        'Desecrate',
        'Despair',
        'Destructive_Link',
        'Determination',
        'Detonate_Dead',
        'Detonate_Dead_of_Chain_Reaction',
        'Detonate_Dead_of_Scavenging',
        'Detonate_Mines',
        'Devouring_Totem',
        'Discharge',
        'Discharge_of_Misery',
        'Discipline',
        'Divine_Ire',
        'Divine_Ire_of_Disintegration',
        'Divine_Ire_of_Holy_Lightning',
        'Divine_Retribution',
        'Dread_Banner',
        'Elemental_Weakness',
        'Energy_Blade',
        'Enfeeble',
        'Essence_Drain',
        'Essence_Drain_of_Desperation',
        'Essence_Drain_of_Wickedness',
        'Ethereal_Knives',
        'Ethereal_Knives_of_Lingering_Blades',
        'Ethereal_Knives_of_the_Massacre',
        'Explosive_Trap',
        'Explosive_Trap_of_Magnitude',
        'Explosive_Trap_of_Shrapnel',
        'Exsanguinate',
        'Exsanguinate_of_Transmission',
        'Eye_of_Winter',
        'Eye_of_Winter_of_Finality',
        'Eye_of_Winter_of_Transience',
        'Faster_Casting_Support',
        'Fire_Trap',
        'Fire_Trap_of_Blasting',
        'Fireball',
        'Firestorm',
        'Firestorm_of_Meteors',
        'Firestorm_of_Pelting',
        'Flame_Dash',
        'Flame_Dash_of_Return',
        'Flame_Link',
        'Flame_Surge',
        'Flame_Surge_of_Combusting',
        'Flame_Wall',
        'Flameblast',
        'Flameblast_of_Celerity',
        'Flameblast_of_Contraction',
        'Flamethrower_Trap',
        'Flamethrower_Trap_of_Stability',
        'Flamewood_Support',
        'Flammability',
        'Flesh_and_Stone',
        'Focused_Channelling_Support',
        'Forbidden_Rite',
        'Forbidden_Rite_of_Soul_Sacrifice',
        'Foulgrasp_Support',
        'Freezing_Pulse',
        'Frost_Bomb',
        'Frost_Bomb_of_Forthcoming',
        'Frost_Bomb_of_Instability',
        'Frost_Shield',
        'Frost_Wall',
        'Frostbite',
        'Frostblink',
        'Frostblink_of_Wintry_Blast',
        'Frostbolt',
        'Frostmage_Support',
        'Frozen_Legion',
        'Frozen_Legion_of_Rallying',
        'Galvanic_Field',
        'Galvanic_Field_of_Intensity',
        'Glacial_Cascade',
        'Glacial_Cascade_of_the_Fissure',
        'Grace',
        'Greater_Spell_Cascade_Support',
        'Greater_Spell_Echo_Support',
        'Haste',
        'Hatred',
        'Herald_of_Ash',
        'Herald_of_Ice',
        'Herald_of_Thunder',
        'Hexblast',
        'Hexblast_of_Contradiction',
        'Hexblast_of_Havoc',
        'Hextoad_Support',
        'Holy_Flame_Totem',
        'Holy_Flame_Totem_of_Ire',
        'Hydrosphere',
        'Ice_Nova',
        'Ice_Nova_of_Deep_Freeze',
        'Ice_Nova_of_Frostbolts',
        'Ice_Spear',
        'Ice_Spear_of_Splitting',
        'Ice_Trap',
        'Ice_Trap_of_Hollowness',
        'Icicle_Mine',
        'Icicle_Mine_of_Fanning',
        'Icicle_Mine_of_Sabotage',
        'Immortal_Call',
        'Impending_Doom_Support',
        'Incinerate',
        'Incinerate_of_Expanse',
        'Incinerate_of_Venting',
        'Intensify_Support',
        'Intuitive_Link',
        'Iron_Will_Support',
        'Lightning_Conduit',
        'Lightning_Conduit_of_the_Heavens',
        'Lightning_Spire_Trap',
        'Lightning_Spire_Trap_of_Overloading',
        'Lightning_Spire_Trap_of_Zapping',
        'Lightning_Tendrils',
        'Lightning_Tendrils_of_Eccentricity',
        'Lightning_Tendrils_of_Escalation',
        'Lightning_Trap',
        'Lightning_Trap_of_Sparking',
        'Lightning_Warp',
        'Malevolence',
        'Manabond',
        'Molten_Shell',
        'Orb_of_Storms',
        'Orb_of_Storms_of_Squalls',
        'Penance_Brand',
        'Penance_Brand_of_Conduction',
        'Penance_Brand_of_Dissipation',
        'Petrified_Blood',
        'Phase_Run',
        'Pinpoint_Support',
        'Plague_Bearer',
        'Poachers_Mark',
        'Precision',
        'Pride',
        'Prismatic_Burst_Support',
        'Protective_Link',
        'Punishment',
        'Purifying_Flame',
        'Purifying_Flame_of_Revelations',
        'Purity_of_Elements',
        'Purity_of_Fire',
        'Purity_of_Ice',
        'Purity_of_Lightning',
        'Pyroclast_Mine',
        'Pyroclast_Mine_of_Sabotage',
        'Reap',
        'Rejuvenation_Totem',
        'Righteous_Fire',
        'Righteous_Fire_of_Arcane_Devotion',
        'Rolling_Magma',
        'Sacred_Wisps_Support',
        'Sacrifice_Support',
        'Scorching_Ray',
        'Scorching_Ray_of_Immolation',
        'Searing_Bond',
        'Seismic_Trap',
        'Seismic_Trap_of_Swells',
        'Shock_Nova',
        'Shock_Nova_of_Procession',
        'Shockwave_Totem',
        'Shockwave_Totem_of_Authority',
        'Sigil_of_Power',
        'Siphoning_Trap',
        'Siphoning_Trap_of_Pain',
        'Smoke_Mine',
        'Snipers_Mark',
        'Soul_Link',
        'Soulrend',
        'Soulrend_of_Reaping',
        'Soulrend_of_the_Spiral',
        'Spark',
        'Spark_of_the_Nova',
        'Spark_of_Unpredictability',
        'Spell_Cascade_Support',
        'Spell_Echo_Support',
        'Spell_Totem_Support',
        'Spellblade_Support',
        'Spellslinger',
        'Steelskin',
        'Storm_Brand',
        'Storm_Brand_of_Indecision',
        'Storm_Burst',
        'Storm_Burst_of_Repulsion',
        'Storm_Call',
        'Storm_Call_of_Trarthus',
        'Stormbind',
        'Stormbind_of_Teleportation',
        'Stormblast_Mine',
        'Tempest_Shield',
        'Temporal_Chains',
        'Temporal_Rift',
        'Tornado',
        'Tornado_of_Elemental_Turbulence',
        'Unearth',
        'Unleash_Support',
        'Vampiric_Link',
        'Vitality',
        'Void_Sphere',
        'Void_Sphere_of_Rending',
        'Volatile_Dead',
        'Volatile_Dead_of_Confinement',
        'Volatile_Dead_of_Seething',
        'Voltaxic_Burst',
        'Vortex',
        'Vortex_of_Projection',
        'Vulnerability',
        'Wall_of_Force',
        'War_Banner',
        'Warlords_Mark',
        'Wave_of_Conviction',
        'Wave_of_Conviction_of_Trarthus',
        'Winter_Orb',
        'Wintertide_Brand',
        'Wither',
        'Withering_Step',
        'Wrath',
        'Zealotry',
    ]
    
    url_base = 'https://www.poewiki.net/wiki/'
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    all_gem_results = []
    
    for gem_name in gem_names:
        print(f">>> Processing gem: {gem_name}")
        url = f"{url_base}{gem_name}"
        
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            html = response.text
            
            # 1. Locate the item-box -gem span
            container_tag = '<span class="item-box -gem">'
            container_start = html.find(container_tag)
            
            if container_start == -1:
                print(f"  Warning: {container_tag} not found for {gem_name}")
                continue
                
            # Find the end of this container span
            container_end = find_matching_closing_tag(html, container_start, 'span')
            target_data = html[container_start:container_end]
            
            # --- New Extraction Logic ---
            # 1. Extract info_name from header
            info_name = ""
            header_match = re.search(r'<span class="header -single">.*?<span class="symbol"></span>(.*?)<span class="symbol"></span></span>', target_data)
            if header_match:
                info_name = re.sub(r'<[^>]+>', '', header_match.group(1)).strip()
            
            # 2. Extract tags
            # Tags are located before the first "Level:" or "<br>" within the item-stats
            tags = []
            # Find the section containing tags (usually links before a <br>)
            tags_part_match = re.search(r'<span class="group">(.*?)<br\s*/?>\s*Level:', target_data, re.DOTALL)
            if tags_part_match:
                tags_html = tags_part_match.group(1)
                # Find all link text which represents gems
                found_tags = re.findall(r'<a[^>]*>(.*?)</a>', tags_html)
                tags = [re.sub(r'<[^>]+>', '', t).strip() for t in found_tags if t.strip()]
            
            # 3. Process the remaining content into lines
            # To avoid repeating name/tags in lines, we split target_data at the first "Level:"
            lines_start_index = target_data.find('Level:')
            if lines_start_index == -1:
                # Fallback to after header if Level is somehow missing
                lines_start_index = target_data.find('</span>', target_data.find('header -single'))
            
            lines_content = target_data[lines_start_index:] if lines_start_index != -1 else target_data
            
            # Replace common block and link tags with newlines to separate stats
            lines_content = re.sub(r'<br\s*/?>', '\n', lines_content)
            lines_content = re.sub(r'</?(span|div|p|h[1-6]|li|tr|td|a)[^>]*>', '\n', lines_content)
            
            # Strip all remaining HTML tags
            clean_text = re.sub(r'<[^>]+>', '', lines_content)
            
            # Handle entities
            clean_text = clean_text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
            
            # Normalize and filter lines
            raw_lines = clean_text.split('\n')
            gem_lines = []
            for line in raw_lines:
                line = line.strip()
                line = " ".join(line.split())
                
                # Cutoff at Acquisition
                if "Acquisition" in line:
                    break
                    
                if line and len(line) > 1:
                    # Filter out purely numeric lines unless they look like level requirements
                    if line.isdigit() and len(line) < 3:
                        continue
                    # Filter out common wiki UI words
                    if line in ["v", "t", "e", "Edit", "Contents"]:
                        continue
                    if not gem_lines or gem_lines[-1] != line:
                        gem_lines.append(line)
            
            all_gem_results.append({
                'name': gem_name.replace('_', ' '),
                'wiki_name': gem_name,
                'info_name': info_name,
                'tags': tags,
                'lines': gem_lines
            })
            
        except Exception as e:
            print(f"  Error processing {gem_name}: {e}")
            
    return all_gem_results

def main():
    print("Starting gem data pull...")
    gems = pull_gems()
    
    # Save to data/gems.json
    os.makedirs('data', exist_ok=True)
    output_path = 'data/gems.json'
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(gems, f, indent=2, ensure_ascii=False)
        
    print(f"\nSuccessfully processed {len(gems)} gems.")
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    main()
