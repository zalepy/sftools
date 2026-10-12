import math
from typing import Dict, List, Optional, Tuple

from sftools.domain.enums.demand_type import DemandType
from sftools.domain.enums.recipe_type import RecipeType
from sftools.domain.models.demand import Demand
from sftools.domain.models.factory_graph import FactoryGraph
from sftools.domain.models.item import Item
from sftools.domain.models.production_node import ProductionNode
from sftools.domain.models.recipe import Recipe


RECIPE_TYPE_ORDER = {RecipeType.BASIC: 0, RecipeType.CONVERSION: 1, RecipeType.ALTERNATE: 2}


def default_recipe_for(item: Item) -> Optional[Recipe]:
    """
    The recipe used for a demand of `item` until the user switches it. In order of preference:
    1. not unpackaging (Unpackage X needs Packaged X, which is made from X)
    2. item as main product before by-product (by-product chains such as
       Compacted Coal <- Ionized Fuel <- Rocket Fuel <- Turbofuel <- Compacted Coal loop back)
    3. basic, then converter, then alternate recipes
    4. the recipe named after the item, then the order in the game data
    """
    def rank(indexed):
        index, recipe = indexed
        return (
            recipe.name.startswith('Unpackage'),
            not recipe.is_main_product(item.name),
            RECIPE_TYPE_ORDER[recipe.type],
            recipe.name != item.name,
            index,
        )

    candidates = [(i, r) for i, r in enumerate(item.recipes) if r.produces(item.name) and r.rate_of(item.name)]
    if not candidates:
        return None
    return min(candidates, key=rank)[1]


def root_node_ids(item_names: List[str]) -> List[str]:
    """Root nodes are keyed by item; a repeated item gets '#2', '#3', ... in order."""
    seen: Dict[str, int] = {}
    ids = []
    for name in item_names:
        seen[name] = seen.get(name, 0) + 1
        ids.append(name if seen[name] == 1 else f"{name}#{seen[name]}")
    return ids


def child_node_id(parent: ProductionNode, item_name: str, items_map: Dict = None) -> str:
    """
    '<parent id>__<item>', whatever recipe the parent runs: when the parent switches recipe, the inputs
    both recipes use keep their nodes (and the adjustments made on them).
    """
    return f"{parent.id}__{item_name}"


def split_parts(node_id: str, rate: float, splits: Optional[Dict[str, int]]) -> List[Tuple[str, float]]:
    """
    (node id, rate) for each part of a node: a node split into k parts is k nodes with an equal share
    of its demand. Part 1 keeps the node's ID, so its adjustments stay; the others are '<id>~2', '<id>~3', ...
    """
    count = (splits or {}).get(node_id, 1)
    if count < 2:
        return [(node_id, rate)]
    return [(node_id if part == 1 else f"{node_id}~{part}", rate / count) for part in range(1, count + 1)]


def calculate_demands(items_map, root_demands_list: List[Demand], scale_overrides: Dict[str, float] = None, round_up: bool = True,
                      splits: Optional[Dict[str, int]] = None) -> FactoryGraph:
    if scale_overrides is None:
        scale_overrides = {}

    graph = FactoryGraph()

    # Queue: (Demand, NodeId, ParentNode, items produced by the ancestors)
    # ParentNode is None for roots
    queue: List[Tuple[Demand, str, Optional[ProductionNode], frozenset]] = []

    root_ids = root_node_ids([d.item.name for d in root_demands_list])
    for d, root_id in zip(root_demands_list, root_ids):
        queue.append((d, root_id, None, frozenset()))

    processed_count = 0
    max_nodes = 5000 # Safety brake

    while queue and processed_count < max_nodes:
        current_demand, node_id, parent_node, ancestors = queue.pop(0)

        if current_demand.type == DemandType.SINK:
            # Sinks are terminal for this logic, we don't produce them
            continue
        if current_demand.item.name in ancestors:
            # The item is already being made further up this chain; treat it as an input
            continue

        item = items_map.get(current_demand.item.name)
        if not item or not item.recipes:
            continue

        recipe = default_recipe_for(item)
        if recipe is None:
            continue

        for part_id, target_rate in split_parts(node_id, current_demand.rate, splits):
            # Calculate Base Scaler from demand rate
            base_scaler = target_rate / recipe.rate_of(item.name)

            # Apply rounding (only for initial generation when no override exists)
            if part_id in scale_overrides:
                # Use the scale override directly - this is the building multiplier
                scaler = scale_overrides[part_id]
            elif round_up:
                # Round up to next integer for buildings
                scaler = math.ceil(base_scaler - 0.00001) # epsilon for float precision
                if scaler == 0 and base_scaler > 0: scaler = 1 # Safety
            else:
                scaler = base_scaler

            # Create Node
            node = recipe.generate_production_node(part_id, scaler, item.name)
            node.ideal_building_scale = base_scaler

            # Track where demand came from
            if parent_node:
                node.parent_demands[parent_node.id] = target_rate
            else:
                node.parent_demands["External Demand"] = target_rate
                node.external_demand = target_rate

            graph.add_node(node)

            # Link Graph
            if parent_node:
                graph.link(parent_node, node)

            # Enqueue Sub-Demands for the recipe
            for sd in recipe.generate_demands(scaler, item.name):
                queue.append((sd, child_node_id(node, sd.item.name, items_map), node, ancestors | {item.name}))

            processed_count += 1

    return graph


def _ancestor_items(node: ProductionNode) -> frozenset:
    """Items produced by `node` and the nodes above it in the original tree (node IDs are paths)."""
    items = set()
    current = node
    while current is not None:
        items.add(current.output_item_name)
        current = next((p for p in current.parents if current.id.startswith(p.id + '__')), None)
    return frozenset(items)


def expand_new_subtree(graph: FactoryGraph, parent_node: ProductionNode, items_map: Dict, round_up: bool = True,
                       splits: Optional[Dict[str, int]] = None):
    """
    Expands a new subtree from an existing node that just had its recipe changed.
    Checks for existing dormant nodes before creating new ones.
    """
    if not parent_node.recipe:
        return

    # Queue of (Demand, ParentNodePath, ParentNode)
    # We start with the sub-demands of the parent_node
    queue = []
    ancestors = _ancestor_items(parent_node)
    # Use effective scale for initial sub-demands
    sub_demands = parent_node.recipe.generate_demands(parent_node.building_scale, parent_node.output_item_name)
    for sd in sub_demands:
        queue.append((sd, child_node_id(parent_node, sd.item.name, items_map), parent_node, ancestors))

    processed_count = 0
    max_nodes = 1000 # Smaller brake for subtree

    while queue and processed_count < max_nodes:
        current_demand, node_id, p_node, ancestors = queue.pop(0)

        if current_demand.type == DemandType.SINK:
            continue
        if current_demand.item.name in ancestors:
            continue

        item = items_map.get(current_demand.item.name)
        if not item or not item.recipes:
            continue

        recipe = default_recipe_for(item)
        if recipe is None:
            continue

        for part_id, target_rate in split_parts(node_id, current_demand.rate, splits):
            # Check if node already exists
            existing_node = graph.get_node(part_id)
            if existing_node:
                # Re-activate it and its subtree
                graph.set_subtree_dormancy(part_id, False)
                # Update demand from parent
                existing_node.parent_demands[p_node.id] = target_rate
                # Ensure link exists (though it should if it was a child before)
                graph.link(p_node, existing_node)
                continue

            # Create New Node
            base_scaler = target_rate / recipe.rate_of(item.name)
            scaler = math.ceil(base_scaler - 0.00001) if round_up else base_scaler
            if round_up and scaler == 0 and base_scaler > 0: scaler = 1

            node = recipe.generate_production_node(part_id, scaler, item.name)
            node.recipe = recipe
            node.ideal_building_scale = base_scaler
            node.parent_demands[p_node.id] = target_rate

            graph.add_node(node)
            graph.link(p_node, node)

            # Recurse
            for sd in recipe.generate_demands(scaler, item.name):
                queue.append((sd, child_node_id(node, sd.item.name, items_map), node, ancestors | {item.name}))

            processed_count += 1


def recalculate_graph(graph: FactoryGraph, overrides: Optional[Dict[str, float]] = None, round_up: bool = False):
    """
    Recalculates the scales of nodes based on user overrides and parent requirements.
    This is now a wrapper around FactoryGraph.recalculate.
    """
    graph.recalculate(overrides, round_up)
    return graph

def switch_recipe_in_graph(graph: FactoryGraph, node_id: str, new_recipe: Recipe, items_map: Dict, round_up: bool = True,
                           splits: Optional[Dict[str, int]] = None):
    """
    Switches the recipe for a node, proactively deactivating its current subtree
    and activating/expanding the new one.
    """
    node = graph.get_node(node_id)
    if not node:
        return

    # 1. Deactivate old subtree
    # Important: only deactivate children, not the node itself
    for child in list(node.children):
        graph.set_subtree_dormancy(child.id, True)

    # 2. Swap Recipe
    node.update_from_recipe(new_recipe)
    node.is_dormant = False # Ensure it's active

    # 3. Activate/Expand New Subtree
    expand_new_subtree(graph, node, items_map, round_up, splits)

    # 4. Recalculate everything
    graph.recalculate(round_up=round_up)


ACTIVE, DROPPED, MISSING = "active", "dropped", "missing"


def _entry_state(graph: FactoryGraph, node_id: str) -> str:
    """
    ACTIVE: the node runs. DROPPED: the node, or the closest ancestor that exists, is dormant: it is an
    input (or under an input) that the recipe now running above it doesn't use. MISSING: anything else,
    usually an entry from an older saved plan.
    """
    node = graph.get_node(node_id)
    if node is not None:
        return DROPPED if node.is_dormant else ACTIVE
    end = len(node_id)
    while (end := node_id.rfind('__', 0, end)) != -1:
        ancestor = graph.get_node(node_id[:end])
        if ancestor is not None:
            return DROPPED if ancestor.is_dormant else MISSING
    return MISSING


def _drop_unused_inputs_of_merged(graph: FactoryGraph) -> bool:
    """
    A merge group runs its target's recipe. Inputs of the absorbed nodes that this recipe doesn't use
    are dropped, with everything under them. Returns whether anything was dropped.
    """
    active = {node_id: node for node_id, node in graph.all_nodes.items() if not node.is_dormant}
    dropped = False
    for node in active.values():
        if not node.absorbed_by:
            continue
        rep = graph._representative(node, active)
        needed = {item.name for item, _ in rep.recipe.ingredients} if rep.recipe else set()
        for child in graph._original_children(node):
            if not child.is_dormant and child.output_item_name not in needed:
                graph.drop_subtree(child.id)
                dropped = True
    return dropped


MIN_CLOCK, MAX_CLOCK = 0.01, 2.5
OVERRIDES_RETIRED = "building counts are no longer set directly; set clock speeds instead"


def parse_clock_groups(groups) -> Tuple[float, List[Tuple[int, float]]]:
    """
    A node's clocks, e.g. [{"clock": 1.0}, {"count": 1, "clock": 0.6}]: exactly one group without a count
    (the clock of as many buildings as the demand needs) and any number of fixed groups, such as the
    last building. Returns (rest clock, [(count, clock), ...]); raises ValueError with the reason.
    """
    if not isinstance(groups, list) or not groups:
        raise ValueError("expected a list of clock groups")
    rest, fixed = [], []
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("clock"), (int, float)):
            raise ValueError("each group needs a clock")
        clock = float(group["clock"])
        if not MIN_CLOCK <= clock <= MAX_CLOCK:
            raise ValueError(f"clock {clock:.0%} is outside {MIN_CLOCK:.0%}-{MAX_CLOCK:.0%}")
        count = group.get("count")
        if count is None:
            rest.append(clock)
        elif isinstance(count, int) and not isinstance(count, bool) and count >= 1:
            fixed.append((count, clock))
        else:
            raise ValueError("a group's count must be a whole number of at least 1")
    if len(rest) != 1:
        raise ValueError("exactly one group must have no count")
    return rest[0], fixed


def build_plan(
    items_map: Dict,
    recipes_map: Dict[str, Recipe],
    demands: List[Tuple[str, float]],
    round_up: bool = True,
    recipes: Optional[Dict[str, str]] = None,
    merges: Optional[Dict[str, str]] = None,
    overrides: Optional[Dict[str, float]] = None,
    splits: Optional[Dict[str, int]] = None,
    clocks: Optional[Dict[str, list]] = None,
) -> FactoryGraph:
    """
    Builds a FactoryGraph from the full plan description.
    The API is stateless: every request replays demands (with splits) -> recipe switches -> merges -> clocks.
    Building counts follow the demand and the clocks (see parse_clock_groups, FactoryGraph._set_scale);
    `overrides` (building counts set directly) are retired and reported in `ignored`.
    Splits apply as nodes are created (see split_parts), so the parts of a split node, and their
    inputs, exist before any other entry refers to them.

    A recipe switch keeps the inputs both recipes use, drops the inputs the new recipe doesn't use
    (with everything under them) and builds the new ones. A merge group runs its target's recipe, so
    the absorbed nodes' inputs that it doesn't use are dropped the same way.

    Entries that can't apply are skipped and listed in `graph.ignored` as
    {"kind": "recipe" | "merge" | "override" | "split" | "clock", "node_id", "reason"}. Entries on dropped
    inputs also have "dropped": True: they belonged to a branch the current recipes no longer use, and
    a new branch starts fresh. When a merge target is dropped, the nodes merged into it stay merged
    with each other: those entries carry "replacement", their new target.
    """
    ignored = []
    splits = dict(splits or {})
    for node_id, count in list(splits.items()):
        if count < 2:
            ignored.append({"kind": "split", "node_id": node_id, "reason": f"needs at least 2 parts, got {count}"})
            del splits[node_id]

    root_demands = [Demand(name, items_map[name], rate, DemandType.PRODUCE) for name, rate in demands]
    graph = calculate_demands(items_map, root_demands, round_up=round_up, splits=splits)

    def report(kind: str, node_id: str, state: str, **extra):
        if state == DROPPED:
            ignored.append({"kind": kind, "node_id": node_id, "reason": "input not used by the current recipe",
                            "dropped": True, **extra})
        else:
            ignored.append({"kind": kind, "node_id": node_id, "reason": "node not in plan", **extra})

    # Parents first: a child's ID extends its parent's ID, so shorter IDs are switched first.
    for node_id, recipe_name in sorted((recipes or {}).items(), key=lambda kv: len(kv[0])):
        state = _entry_state(graph, node_id)
        if state != ACTIVE:
            report("recipe", node_id, state)
            continue
        node = graph.get_node(node_id)
        recipe = recipes_map.get(recipe_name)
        if recipe is None:
            ignored.append({"kind": "recipe", "node_id": node_id, "reason": f"unknown recipe {recipe_name!r}"})
            continue
        if not recipe.produces(node.output_item_name):
            ignored.append({"kind": "recipe", "node_id": node_id,
                            "reason": f"{recipe_name!r} does not produce {node.output_item_name}"})
            continue
        if node.recipe is not recipe:
            switch_recipe_in_graph(graph, node_id, recipe, items_map, round_up=round_up, splits=splits)

    # Merging can drop inputs (of the absorbed nodes), which can drop nodes other merges refer to:
    # apply the merges again until nothing more is dropped.
    while True:
        merge_ignored = []
        graph.merges = {}
        graph._reset_structure()
        by_target: Dict[str, List[str]] = {}
        for source_id, target_id in (merges or {}).items():
            states = {n: _entry_state(graph, n) for n in (source_id, target_id)}
            stale = [n for n, state in states.items() if state == MISSING]
            if stale:
                merge_ignored.append({"kind": "merge", "node_id": source_id,
                                      "reason": f"node not in plan: {', '.join(stale)}"})
            elif states[source_id] == DROPPED:
                merge_ignored.append({"kind": "merge", "node_id": source_id,
                                      "reason": "input not used by the current recipe", "dropped": True})
            else:
                by_target.setdefault(target_id, []).append(source_id)
        for target_id, sources in by_target.items():
            if _entry_state(graph, target_id) == DROPPED:
                # The rest of the group stays merged, into its first remaining node
                new_target, *others = sources
                merge_ignored.append({"kind": "merge", "node_id": new_target,
                                      "reason": "merge target not used by the current recipe", "dropped": True})
                for source_id in others:
                    merge_ignored.append({"kind": "merge", "node_id": source_id,
                                          "reason": "merge target not used by the current recipe", "dropped": True,
                                          "replacement": new_target})
                    graph.apply_merge(source_id, new_target)
            else:
                for source_id in sources:
                    graph.apply_merge(source_id, target_id)
        if not _drop_unused_inputs_of_merged(graph):
            break
    ignored.extend(merge_ignored)

    for node_id in list(splits):
        state = _entry_state(graph, node_id)
        if state != ACTIVE:
            report("split", node_id, state)
            del splits[node_id]

    for node_id in overrides or {}:
        ignored.append({"kind": "override", "node_id": node_id, "reason": OVERRIDES_RETIRED})

    graph.clocks = {}
    for node_id, groups in (clocks or {}).items():
        try:
            parsed = parse_clock_groups(groups)
        except ValueError as ex:
            ignored.append({"kind": "clock", "node_id": node_id, "reason": str(ex)})
            continue
        state = _entry_state(graph, node_id)
        if state != ACTIVE:
            report("clock", node_id, state)
            continue
        graph.clocks[node_id] = parsed

    graph.recalculate({}, round_up=round_up)
    graph.ignored = ignored
    graph.splits = splits
    return graph
