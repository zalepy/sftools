"""
Make something from a by-product (ticket 059): a branch running a recipe that takes what's left of a node's
by-product, after the plan's uses of it. The maker's own rate sets the branch's size, so it's supply-driven
without deciding which side drives the graph.

The branch is a root (id '<maker>~<item>') with its own recipe, demanded at what that much of the by-product
makes. Its input of the by-product is covered by the maker (a use, MAKE counting as USE), so that input's own
node and everything under it have nothing to make; its other inputs are made or mined as usual. Its clock is
fitted so it takes exactly what's left: as many buildings as that needs at the node's clock (100%, or the
one the plan sets), all at the same clock. What's left is only known once the plan is calculated, so
supply.build_powered_plan calculates again with the branches.
"""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sftools.domain.models.factory_graph import NEGLIGIBLE, FactoryGraph
from sftools.domain.models.power import GENERATORS
from sftools.domain.models.recipe import Recipe
from sftools.domain.models.residue import BURN_ID


@dataclass(frozen=True)
class Branch:
    root_id: str
    maker: str
    byproduct: str
    recipe: str
    item: str  # what it makes
    rate: float  # of `item`
    scale: float  # buildings' worth at 100%
    to: str  # "sink" or "supply"


def branch_id(maker: str, byproduct: str) -> str:
    return f"{maker}~{byproduct}"


def find_branches(graph: FactoryGraph, recipes_map: Dict[str, Recipe]) -> List[Branch]:
    """A branch for each Make from it whose maker has some of the by-product left after the plan's uses."""
    found = []
    for (maker, byproduct), make in sorted(graph.byproduct_makes.items()):
        node = graph.all_nodes.get(maker)
        if node is None or node.is_dormant or node.absorbed_by or maker in graph.unused:
            continue
        root_id = branch_id(maker, byproduct)
        used = graph.byproduct_used.get((maker, byproduct), {})
        uses = sum(rate for consumer, rate in used.items()
                   if consumer not in (root_id, BURN_ID) and consumer not in GENERATORS)
        left = graph._byproduct_made(maker, byproduct) - uses
        if left < NEGLIGIBLE:
            continue
        recipe = recipes_map[make["recipe"]]
        per_building = next(rate for item, rate in recipe.ingredients if item.name == byproduct)
        scale = left / per_building
        item = recipe.output_item.name
        found.append(Branch(root_id, maker, byproduct, recipe.name, item, scale * recipe.rate_of(item), scale,
                            make["to"]))
    return found


def fitted_clocks(branch: Branch, groups: Optional[list]) -> List[Dict]:
    """The branch's clock: its buildings all at one clock, taking exactly what's left of the by-product."""
    rest = next((g["clock"] for g in groups or [] if isinstance(g, dict) and "count" not in g
                 and isinstance(g.get("clock"), (int, float)) and g["clock"] > 0), 1.0)
    count = max(1, math.ceil(branch.scale / rest - 1e-9))
    return [{"clock": branch.scale / count}]


def settled(old: List[Branch], new: List[Branch]) -> bool:
    key = lambda branches: [(b.root_id, b.recipe, b.to) for b in branches]  # noqa: E731
    return key(old) == key(new) and all(abs(a.scale - b.scale) <= 1e-6 for a, b in zip(old, new, strict=True))


def as_roots(branches: List[Branch]) -> List[Tuple[str, str, float, str]]:
    """For build_plan: (root id, item, rate, recipe)."""
    return [(b.root_id, b.item, b.rate, b.recipe) for b in branches]
