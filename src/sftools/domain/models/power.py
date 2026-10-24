"""
Generators burning fuel for power (tickets 055, 057), shown as nodes with no output: the Fuel Generators
burning the residue's Fuel, and in a supply-driven plan the generators burning the demanded fuels. One node
per kind of generator; a generator burns one fuel at a time, so the node counts them per fuel.

Only the Nuclear Power Plant is in the scraped data, so the generators are constants (satisfactory.wiki.gg,
checked 2026-10-24). As many generators as the fuel needs at 100%, without clocks: the last ones are underfed
and burn with gaps, so the count follows the fuel with nothing to readjust. Power is what the fuel gives on
average; water and waste follow the fuel burned the same way.
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from sftools.domain.models.factory_graph import EPSILON, FactoryGraph
from sftools.domain.models.residue import BURN_ID, GENERATORS_ID

WATER = "Water"


@dataclass(frozen=True)
class Generator:
    name: str
    power: float  # MW at 100%
    fuels: Dict[str, float]  # fuel -> per minute at 100%
    water: float = 0.0  # per minute at 100%
    waste: Dict[str, Tuple[str, float]] = field(default_factory=dict)  # fuel -> (waste item, per minute)


# Node ids; the Fuel Generators keep the id they had for the residue (ticket 055)
GENERATORS: Dict[str, Generator] = {
    GENERATORS_ID: Generator("Fuel Generator", 250, {
        "Fuel": 20, "Liquid Biofuel": 20, "Turbofuel": 7.5, "Rocket Fuel": 25 / 6, "Ionized Fuel": 3}),
    "coal-generators": Generator("Coal Generator", 75, {
        "Coal": 15, "Compacted Coal": 50 / 7, "Petroleum Coke": 25}, water=45),
    "nuclear-plants": Generator("Nuclear Power Plant", 2500, {
        "Uranium Fuel Rod": 0.2, "Plutonium Fuel Rod": 0.1, "Ficsonium Fuel Rod": 1}, water=240,
        waste={"Uranium Fuel Rod": ("Uranium Waste", 10), "Plutonium Fuel Rod": ("Plutonium Waste", 1)}),
}
# Fuel -> the generators burning it. Biomass Burner fuels (not fully automated) and Alien Power Matrix are left out.
FUELS: Dict[str, str] = {fuel: gen_id for gen_id, gen in GENERATORS.items() for fuel in gen.fuels}


def water_demands(fuels: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    """(generators id, water per minute) for the generators burning these (fuel, rate), in GENERATORS order."""
    water: Dict[str, float] = {}
    for fuel, rate in fuels:
        gen_id = FUELS[fuel]
        gen = GENERATORS[gen_id]
        if gen.water:
            water[gen_id] = water.get(gen_id, 0.0) + rate / gen.fuels[fuel] * gen.water
    return [(gen_id, water[gen_id]) for gen_id in GENERATORS if gen_id in water]


def generator_nodes(graph: FactoryGraph, shown: List[Dict]) -> List[Dict]:
    """
    The generators fed by the shown nodes: the burn Refinery's Fuel, and the roots in `graph.generator_roots`
    (a supply-driven plan's fuels and water). Those roots now feed the generators instead of the user's
    demand, so they're pointed at them (no demand circle), and so are by-products covering their demand.
    """
    feeds: Dict[str, Dict[str, float]] = {}  # generators id -> {fuel: rate}
    water: Dict[str, float] = {}
    children: Dict[str, List[str]] = {}
    rerouted: Dict[Tuple[str, str], str] = {}  # (root id, its item) -> generators id
    for data in shown:
        node_id, item = data["id"], data["output_item"]
        if node_id == BURN_ID:
            gen_id, rate = GENERATORS_ID, data["parent_demands"].get(GENERATORS_ID, 0.0)
        elif node_id in graph.generator_roots:
            gen_id, rate = graph.generator_roots[node_id], data["external_demand"]
            data["parents"] = sorted({*data["parents"], gen_id})
            data["parent_demands"][gen_id] = data["parent_demands"].pop("External Demand", 0.0)
            data["external_demand"] = 0.0
            rerouted[(node_id, item)] = gen_id
        else:
            continue
        if rate <= EPSILON:
            continue
        children.setdefault(gen_id, []).append(node_id)
        if item == WATER:
            water[gen_id] = water.get(gen_id, 0.0) + rate
        else:
            feeds.setdefault(gen_id, {})[item] = feeds.get(gen_id, {}).get(item, 0.0) + rate
    for data in shown:
        for byproduct in data.get("byproducts") or []:
            byproduct["used"] = {rerouted.get((consumer, byproduct["item"]), consumer): rate
                                 for consumer, rate in byproduct["used"].items()}
    return [_node(gen_id, feeds[gen_id], water.get(gen_id, 0.0), children[gen_id]) for gen_id in GENERATORS
            if gen_id in feeds]


def _node(gen_id: str, feeds: Dict[str, float], water: float, children: List[str]) -> Dict:
    """
    The generators in the shape of a serialized node. `generators`: {fuel (all fuels burned), fed (generators'
    worth of fuel), power, water, fuels: [{item, rate, fed, count}]}; their waste is a by-product for the Sink.
    """
    gen = GENERATORS[gen_id]
    fuels = []
    for item, rate in feeds.items():
        fed = rate / gen.fuels[item]
        fuels.append({"item": item, "rate": rate, "fed": fed, "count": math.ceil(fed - EPSILON)})
    fed = sum(f["fed"] for f in fuels)
    count = sum(f["count"] for f in fuels)
    power = fed * gen.power
    inputs = [{"item": f["item"], "rate": f["rate"]} for f in fuels] + ([{"item": WATER, "rate": water}] if water else [])
    base_inputs = [{"item": f["item"], "rate": gen.fuels[f["item"]]} for f in fuels] \
        + ([{"item": WATER, "rate": gen.water}] if gen.water else [])
    byproducts = [{
        "item": gen.waste[f["item"]][0], "rate": f["fed"] * gen.waste[f["item"]][1], "fuel": f["item"],
        "fluid": False, "waste": True,
        "burn": False, "choice": "sink", "loop": False, "solving": False, "settled": True, "rounds": 0, "used": {},
    } for f in fuels if f["item"] in gen.waste]
    return {
        "id": gen_id, "name": gen.name, "recipe_name": gen.name, "building": gen.name,
        "building_scale": fed, "original_building_scale": fed, "buildings": count,
        "clocks": [{"count": count, "clock": 1.0}], "power_shards": 0, "ideal_building_scale": fed,
        "throughput": power, "power": power, "output_item": "Power",
        "parents": [], "children": sorted(children), "parent_demands": {},
        "scaled_inputs": inputs, "base_output_rate": 0, "base_inputs": base_inputs, "base_power": gen.power,
        "is_dormant": False, "is_alternate": False, "is_supplied": False,
        "derivation": [], "is_merged": False, "constituent_ids": [], "constituent_derivations": [],
        "byproducts": byproducts,
        "generators": {"fuel": sum(f["rate"] for f in fuels), "fed": fed, "power": power, "water": water,
                       "fuels": fuels},
    }


def power_summary(nodes: List[Dict]) -> Dict[str, float]:
    """Power generated (gross) and what's left after the plan's own consumption (net), in MW."""
    return {"gross": sum(n["power"] for n in nodes if n.get("generators")), "net": sum(n["power"] for n in nodes)}
