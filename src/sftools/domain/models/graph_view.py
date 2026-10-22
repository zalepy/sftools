"""
What the UI gets from a calculated FactoryGraph: the shown nodes (a merge group as its target), their
by-products, the Sink and inbound production in the shape of nodes, and each node's derivation.
"""
import math
from typing import Dict, List, Optional

from sftools.domain.enums.item_categories import ItemCategory
from sftools.domain.enums.recipe_type import RecipeType
from sftools.domain.models.factory_graph import EPSILON, NEGLIGIBLE, FactoryGraph, external_demand
from sftools.domain.models.production_node import ProductionNode

INBOUND_PREFIX = "inbound:"  # ID of the node showing an item's inbound production, e.g. 'inbound:Iron Ingot'
SINK_ID = "sink"
# The AWESOME Sink isn't in the scraped data. 30 MW each (satisfactory.wiki.gg); it takes one belt, so one
# sink per 1200 items/min (a Mk.6 belt) until belt tiers are planned (ticket 028).
SINK_POWER = 30
SINK_INPUT_RATE = 1200
FLUIDS = {ItemCategory.LIQUIDS, ItemCategory.GAS}  # can't be sunk


def ui_nodes(graph: FactoryGraph) -> List[Dict]:
    """
    Serialized nodes for the UI. A merge group is shown as its target alone: absorbed and dormant
    nodes are left out, links to absorbed nodes point to their target, and the target lists its
    absorbed nodes in `constituent_ids` / `constituent_derivations`. The target's scale and rates
    already cover the whole group (see recalculate).
    """
    shown = []
    target_to_constituents: Dict[str, List[ProductionNode]] = {}

    for node in graph.all_nodes.values():
        if node.absorbed_by:
            target_id = node.absorbed_by
            if target_id not in target_to_constituents:
                target_to_constituents[target_id] = []
            target_to_constituents[target_id].append(node)

    hidden = set(graph.unused)
    for node in graph.all_nodes.values():
        if node.absorbed_by or node.is_dormant or node.id in hidden:
            continue # Skip absorbed, dormant and unused nodes from top level

        constituents = [c for c in target_to_constituents.get(node.id, []) if not c.is_dormant]

        # Serialize representative
        data = serialize_node(graph, node)

        # Map parents and children to their merge targets for UI consistency
        data["parents"] = sorted(list(set(
            graph.get_node(p_id).absorbed_by or p_id
            for p_id in data["parents"]
            if p_id in graph.all_nodes
        )))
        data["children"] = sorted(list(set(
            graph.get_node(c_id).absorbed_by or c_id
            for c_id in data["children"]
            if c_id in graph.all_nodes
        ) - hidden) + [INBOUND_PREFIX + item for item, used in graph.inbound_used.items() if node.id in used])

        # Mark if it's a merged node and track constituents
        data["is_merged"] = len(constituents) > 0
        data["constituent_ids"] = [c.id for c in constituents]
        data["constituent_derivations"] = [derivation(graph, c) for c in constituents]
        data["byproducts"] = byproducts_of(graph, node)
        # What the user demands of the group (demand rows), even where inbound production covers it
        data["external_demand"] = sum(external_demand(member) for member in [node, *constituents])

        shown.append(data)

    sink = sink_node(graph, [data["id"] for data in shown])
    shown.extend(inbound_node(graph, item) for item in graph.inbound)
    if sink:
        shown.append(sink)
    return shown


def byproducts_of(graph: FactoryGraph, node: ProductionNode) -> List[Dict]:
    """
    The node's by-products: {item, rate made, fluid, choice (USE or SINK), loop (a use left out as a
    loop), used ({consumer id: rate} covered by it)}. What isn't used goes to the Sink.
    """
    if node.recipe is None:
        return []
    return [{
        "item": item.name,
        "rate": rate * node.building_scale,
        "fluid": item.category in FLUIDS,
        "choice": graph.byproduct_choice(node.id),
        "loop": (node.id, item.name) in graph.byproduct_loops,
        "solving": (node.id, item.name) in graph.byproduct_solving,
        "settled": graph.loop_settled, "rounds": graph.loop_rounds,
        "used": {k: v for k, v in graph.byproduct_used.get((node.id, item.name), {}).items() if v > EPSILON},
    } for item, rate in node.recipe.other_outputs(node.output_item_name)]


def sink_node(graph: FactoryGraph, node_ids: List[str]) -> Optional[Dict]:
    """
    The Sink, in the shape of a serialized node, if any shown node has a by-product left after what is
    used as supply: `sink.inputs` lists each ({from, item, rate, fluid, loop}). Fluids can't be sunk; they
    are listed anyway, so the rest of the plan calculates, and `sink.fluids` flags them (ticket 024).
    """
    inputs = []
    for node_id in node_ids:
        for byproduct in byproducts_of(graph, graph.all_nodes[node_id]):
            amount = byproduct["rate"] - sum(byproduct["used"].values())
            if amount >= NEGLIGIBLE:
                inputs.append({"from": node_id, "item": byproduct["item"], "rate": amount,
                               "fluid": byproduct["fluid"], "loop": byproduct["loop"]})
    if not inputs:
        return None
    by_item: Dict[str, float] = {}
    for entry in inputs:
        by_item[entry["item"]] = by_item.get(entry["item"], 0) + entry["rate"]
    total = sum(by_item.values())
    solids = sum(entry["rate"] for entry in inputs if not entry["fluid"])
    count = math.ceil(solids / SINK_INPUT_RATE - EPSILON)
    return {
        "id": SINK_ID, "name": "Sink", "recipe_name": "Sink", "building": "AWESOME Sink",
        "building_scale": count, "original_building_scale": count, "buildings": count,
        "clocks": [], "power_shards": 0, "ideal_building_scale": count,
        "throughput": total, "power": -SINK_POWER * count, "output_item": "Sink",
        "parents": [], "children": [], "parent_demands": {},
        "scaled_inputs": [{"item": item, "rate": rate} for item, rate in sorted(by_item.items())],
        "base_output_rate": 0, "base_inputs": [], "base_power": -SINK_POWER,
        "is_dormant": False, "is_alternate": False, "is_supplied": False,
        "derivation": [], "is_merged": False, "constituent_ids": [], "constituent_derivations": [],
        "sink": {"inputs": inputs, "fluids": sorted({e["item"] for e in inputs if e["fluid"]})},
    }


def inbound_node(graph: FactoryGraph, item: str) -> Dict:
    """An item's inbound production, in the shape of a serialized node: it feeds the nodes that used it."""
    used = graph.inbound_used.get(item, {})
    consumers = {consumer: rate for consumer, rate in used.items() if rate > EPSILON}
    total = sum(consumers.values())
    node_id = INBOUND_PREFIX + item
    return {
        "id": node_id, "name": "Inbound production", "recipe_name": "Inbound production",
        "building": "Outside the plan", "building_scale": total, "original_building_scale": total,
        "buildings": 0, "clocks": [], "power_shards": 0, "ideal_building_scale": total,
        "throughput": total, "power": 0, "output_item": item,
        "parents": sorted(consumers), "children": [],
        "scaled_inputs": [], "parent_demands": consumers, "base_output_rate": 1, "base_inputs": [],
        "base_power": 0, "is_dormant": False, "is_alternate": False, "is_supplied": True,
        "derivation": [{"id": node_id, "item": item, "recipe": "Inbound production", "building": "Outside the plan"}],
        "is_merged": False, "constituent_ids": [], "constituent_derivations": [],
        "inbound": {"rate": graph.inbound[item], "used": total},
    }


def derivation(graph: FactoryGraph, node: ProductionNode) -> List[Dict]:
    """
    How the node came about: one step per node from the root demand down to `node`, with the
    item it makes and the recipe it currently runs. Relies on IDs being paths, where each
    ancestor's ID is a '__'-separated prefix of its descendants' IDs (see child_node_id).
    """
    steps = []
    end = 0
    while True:
        end = node.id.find('__', end)
        prefix = node.id if end == -1 else node.id[:end]
        ancestor = graph.get_node(prefix)
        if ancestor is not None:
            steps.append({
                "id": ancestor.id,
                "item": ancestor.output_item_name,
                "recipe": ancestor.recipe.name if ancestor.recipe else ancestor.name,
                "building": ancestor.building.name,
            })
        if end == -1:
            return steps
        end += 2


def serialize_node(graph: FactoryGraph, node: ProductionNode) -> Dict:
    return {
        "id": node.id,
        "name": node.name,
        "recipe_name": node.name.split('__')[-1] if '__' in node.name else node.name,
        "building": node.building.name,
        "building_scale": node.building_scale,
        "original_building_scale": node.original_building_scale,
        "buildings": node.buildings,
        "clocks": [{"count": count, "clock": clock} for count, clock in node.building_clocks or []],
        "power_shards": node.power_shards,
        "ideal_building_scale": node.ideal_building_scale,
        "throughput": node.scaled_output,
        "power": node.scaled_power,
        "output_item": node.output_item_name,
        "parents": [p.id for p in node.parents],
        "children": [c.id for c in node.children],
        "scaled_inputs": [inp.copy() for inp in node.scaled_inputs],
        "parent_demands": node.parent_demands.copy(),
        "base_output_rate": node.base_output_rate,
        "base_inputs": node.base_inputs,
        "base_power": node.base_power,
        "is_dormant": node.is_dormant,
        "is_alternate": node.recipe is not None and node.recipe.type == RecipeType.ALTERNATE,
        "is_supplied": False,  # production nodes; the inbound node is supplied (see inbound_node)
        "derivation": derivation(graph, node),
    }
