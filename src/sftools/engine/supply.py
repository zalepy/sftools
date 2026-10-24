"""
Supply-driven power plans (ticket 057): with only fuels demanded and the plan's inbound rows as the limit, the
plan grows until the first inbound row is used up, and its fuels are burned in generators (power.py).

The plan is linear in its demands, so one factor does it: a probe at the demand rates as given (fractional
buildings, every inbound row covering all it's asked) measures what the plan asks of each row, and the
smallest rate / ask scales the demands for the plan itself. The demand rates only give the ratio between
fuels. Raw inbound rows only set the limit: the plan mines what it uses, so they're left out of the plan
itself. Other inbound rows stay inbound production.
"""
from typing import Dict, List, Optional, Tuple

from sftools.domain.models.factory_graph import EPSILON, FactoryGraph
from sftools.domain.models.item import Item
from sftools.domain.models.power import FUELS, WATER, water_demands
from sftools.engine.calculator import build_plan, root_node_ids

COVER_ALL = 1e12  # an inbound rate no plan uses up: the probe measures what the plan asks of each row


def eligible(demands: List[Tuple[str, float]], inbound: List[Tuple[str, float]]) -> bool:
    """Only fuels demanded, and at least one inbound row: the plan can use the inbound as its limit."""
    return bool(demands) and bool(inbound) and all(item in FUELS for item, _ in demands)


def is_raw(item: Item) -> bool:
    """Mined, pumped or extracted: made by a recipe with no ingredients."""
    return any(r.produces(item.name) and not r.ingredients for r in item.recipes)


def with_water(fuels: List[Tuple[str, float]]) -> Tuple[List[Tuple[str, float]], Dict[str, str]]:
    """
    The demands for these fuels and their generators' water (one row per kind of generator that needs it),
    and {root node id: generators id} for each.
    """
    water = water_demands(fuels)
    demands = fuels + [(WATER, rate) for _, rate in water]
    ids = root_node_ids([item for item, _ in demands])
    roots = {root_id: FUELS[item] for root_id, (item, _) in zip(ids[:len(fuels)], fuels, strict=True)}
    roots.update({root_id: gen_id for root_id, (gen_id, _) in zip(ids[len(fuels):], water, strict=True)})
    return demands, roots


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
    probe_demands, _ = with_water(demands)
    probe = build_plan(items_map, recipes_map, probe_demands, inbound=[(item, COVER_ALL) for item in limits],
                       exact=True, **plan)
    asked = {item: probe.item_demand.get(item, 0.0) for item in limits}
    factors = {item: limits[item] / asked[item] for item in limits if asked[item] > EPSILON}
    limit: Optional[str] = min(factors, key=factors.get) if factors else None
    factor = factors[limit] if limit else 1.0

    fuels = [(item, rate * factor) for item, rate in demands]
    plan_demands, roots = with_water(fuels)
    raw = {item: is_raw(items_map[item]) for item in limits}
    graph = build_plan(items_map, recipes_map, plan_demands, exact=exact,
                       inbound=[(item, rate) for item, rate in limits.items() if not raw[item]], **plan)
    graph.generator_roots = roots
    return graph, {
        "active": True, "limit": limit, "factor": factor,
        "demands": [{"item": item, "rate": rate} for item, rate in fuels],
        "rows": [{"item": item, "rate": rate, "used": graph.item_demand.get(item, 0.0), "raw": raw[item],
                  "limit": item == limit, "unused": item not in factors} for item, rate in limits.items()],
    }
