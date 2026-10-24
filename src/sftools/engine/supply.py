"""
Supply-driven power plans (ticket 057): with only fuels demanded and the plan's inbound rows as the limit, the
plan grows until the first inbound row is used up, and its fuels are burned in generators (power.py).

The plan is linear in its demands, so one factor does it: a probe at the demand rates as given (fractional
buildings, every inbound row covering all it's asked) measures what the plan asks of each row, and the
smallest rate / ask scales the demands for the plan itself. The demand rates only give the ratio between
fuels. Raw inbound rows only set the limit: the plan mines what it uses, so they're left out of the plan
itself. Other inbound rows stay inbound production.

Every plan goes through build_powered_plan, for the water of generators burning fuel by-products (ticket 058).
"""
from typing import Dict, List, Optional, Tuple

from sftools.domain.models.factory_graph import EPSILON, FactoryGraph
from sftools.domain.models.item import Item
from sftools.domain.models.power import FUELS, GENERATORS, WATER, burned, water_demands
from sftools.engine.calculator import build_plan, root_node_ids

COVER_ALL = 1e12  # an inbound rate no plan uses up: the probe measures what the plan asks of each row


def eligible(demands: List[Tuple[str, float]], inbound: List[Tuple[str, float]]) -> bool:
    """Only fuels demanded, and at least one inbound row: the plan can use the inbound as its limit."""
    return bool(demands) and bool(inbound) and all(item in FUELS for item, _ in demands)


def is_raw(item: Item) -> bool:
    """Mined, pumped or extracted: made by a recipe with no ingredients."""
    return any(r.produces(item.name) and not r.ingredients for r in item.recipes)


def with_water(demands: List[Tuple[str, float]], burning: List[Tuple[str, float]],
               fuel_roots: bool) -> Tuple[List[Tuple[str, float]], Dict[str, str]]:
    """
    The demands and a Water row per kind of generator that needs it for the fuels `burning`, and {root node id:
    generators id} for the Water roots, and for the demands too when they're fuels burned (`fuel_roots`).
    """
    water = water_demands(burning)
    rows = demands + [(WATER, rate) for _, rate in water]
    ids = root_node_ids([item for item, _ in rows])
    roots = {root_id: FUELS[item] for root_id, (item, _) in zip(ids[:len(demands)], demands, strict=True)}         if fuel_roots else {}
    roots.update({root_id: gen_id for root_id, (gen_id, _) in zip(ids[len(demands):], water, strict=True)})
    return rows, roots


def build_powered_plan(items_map: Dict, recipes_map: Dict, demands: List[Tuple[str, float]],
                       fuel_roots: bool = False, **plan) -> FactoryGraph:
    """
    build_plan, with the water its generators need: for the demanded fuels when they're burned (`fuel_roots`,
    a limited plan), and for the fuel by-products burned (ticket 058). Those are only known once the plan is
    calculated, so a plan burning one in generators that need water is calculated again with it. Water roots
    make no by-products, so that settles it.
    """
    burning = list(demands) if fuel_roots else []
    rows, roots = with_water(demands, burning, fuel_roots)
    graph = build_plan(items_map, recipes_map, rows, **plan)
    thirsty = [(fuel, rate) for fuel, rate in burned(graph) if GENERATORS[FUELS[fuel]].water]
    if thirsty:
        rows, roots = with_water(demands, burning + thirsty, fuel_roots)
        graph = build_plan(items_map, recipes_map, rows, **plan)
    graph.generator_roots = roots
    return graph


def build_supply_plan(items_map: Dict, recipes_map: Dict, demands: List[Tuple[str, float]],
                      inbound: List[Tuple[str, float]], exact: bool = False, **plan) -> Tuple[FactoryGraph, Dict]:
    """
    The plan at the scale where its first inbound row is used up, and what the panel shows of it:
    {active, limit (the row used up, or None when the plan uses none of them: then it runs at the rates
    given), factor, demands ([{item, rate}], the fuels as planned), rows ([{item, rate, used, raw, limit,
    unused}]: `used` is what the plan asks, a little over the limit where whole buildings round up)}.
    `plan` takes build_plan's other arguments (recipes, merges, clocks, ...).
    """
    limits: Dict[str, float] = {}
    for item, rate in inbound:
        limits[item] = limits.get(item, 0.0) + rate
    probe = build_powered_plan(items_map, recipes_map, demands, fuel_roots=True,
                               inbound=[(item, COVER_ALL) for item in limits], exact=True, **plan)
    asked = {item: probe.item_demand.get(item, 0.0) for item in limits}
    factors = {item: limits[item] / asked[item] for item in limits if asked[item] > EPSILON}
    limit: Optional[str] = min(factors, key=factors.get) if factors else None
    factor = factors[limit] if limit else 1.0

    fuels = [(item, rate * factor) for item, rate in demands]
    raw = {item: is_raw(items_map[item]) for item in limits}
    graph = build_powered_plan(items_map, recipes_map, fuels, fuel_roots=True, exact=exact,
                               inbound=[(item, rate) for item, rate in limits.items() if not raw[item]], **plan)
    return graph, {
        "active": True, "limit": limit, "factor": factor,
        "demands": [{"item": item, "rate": rate} for item, rate in fuels],
        "rows": [{"item": item, "rate": rate, "used": graph.item_demand.get(item, 0.0), "raw": raw[item],
                  "limit": item == limit, "unused": item not in factors} for item, rate in limits.items()],
    }
