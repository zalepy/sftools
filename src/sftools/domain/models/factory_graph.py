from typing import Dict, List, Optional, Set, Tuple
import math
from sftools.domain.enums.item_categories import ItemCategory
from sftools.domain.enums.recipe_type import RecipeType
from sftools.domain.models.production_node import ProductionNode

EPSILON = 1e-9
# A by-product left over below this (per min) isn't sent to the Sink: it's rounding, e.g. a clock of
# 83.333% for 5/6, and would show as 0.00/min (and, for a fluid, as a Sink that can't take it)
NEGLIGIBLE = 0.005
INBOUND_PREFIX = "inbound:"  # ID of the node showing an item's inbound production, e.g. 'inbound:Iron Ingot'
SINK_ID = "sink"
# The AWESOME Sink isn't in the scraped data. 30 MW each (satisfactory.wiki.gg); it takes one belt, so one
# sink per 1200 items/min (a Mk.6 belt) until belt tiers are planned (ticket 028).
SINK_POWER = 30
SINK_INPUT_RATE = 1200
FLUIDS = {ItemCategory.LIQUIDS, ItemCategory.GAS}  # can't be sunk
USE, SINK, SOLVE = "use", "sink", "solve"  # what a node does with its by-products (tickets 031, 032)
# Solving a by-product loop (see recalculate): rounds until the amounts change by at most LOOP_TOLERANCE
# (per min), like Google Sheets' iterative calculation, but damped
LOOP_ROUNDS = 100
LOOP_TOLERANCE = 1e-6


class FactoryGraph:
    """
    Manages a collection of ProductionNodes and their state (merges, clocks).
    Handles calculation and UI representation.
    """
    def __init__(self, nodes: Dict[str, ProductionNode] = None):
        self.all_nodes = nodes or {}
        self.merges: Dict[str, str] = {} # source_id -> target_id
        self._initial_structure: Dict[str, Dict[str, List[str]]] = {}
        self.ignored: List[Dict] = []  # plan entries build_plan could not apply
        # node_id -> (clock for the rest, [(count, clock), ...] fixed groups such as the last building)
        self.clocks: Dict[str, Tuple[float, List[Tuple[int, float]]]] = {}
        # item -> rate supplied from outside the plan, used before anything is produced (see recalculate)
        self.inbound: Dict[str, float] = {}
        self.inbound_used: Dict[str, Dict[str, float]] = {}  # item -> {consumer id: rate}, set by recalculate
        self.unused: Set[str] = set()  # nodes left with nothing to make (all covered by inbound production)
        # By-products (ticket 031): node id -> USE or SINK as the plan says; others get the default
        self.byproduct_choices: Dict[str, str] = {}
        self.byproduct_default: str = SINK
        # Set by recalculate: (maker id, item) -> {consumer id: rate}, and the uses left out as loops
        self.byproduct_used: Dict[Tuple[str, str], Dict[str, float]] = {}
        self.byproduct_loops: Set[Tuple[str, str]] = set()
        # Loops being solved (choice SOLVE), and how: rounds taken and whether the amounts settled
        self.byproduct_solving: Set[Tuple[str, str]] = set()
        self.loop_rounds = 0
        self.loop_settled = True

    def add_node(self, node: ProductionNode):
        self.all_nodes[node.id] = node
        self._initial_structure.setdefault(node.id, {"parents": [], "children": []})

    def link(self, parent: ProductionNode, child: ProductionNode):
        """
        Connects parent -> child and records the link in the unmerged structure, so it survives
        `_reset_structure` (unmerge). Use this rather than add_child/add_parent when building the graph.
        """
        parent.add_child(child)
        child.add_parent(parent)
        parent_links = self._initial_structure.setdefault(parent.id, {"parents": [], "children": []})
        child_links = self._initial_structure.setdefault(child.id, {"parents": [], "children": []})
        if child.id not in parent_links["children"]:
            parent_links["children"].append(child.id)
        if parent.id not in child_links["parents"]:
            child_links["parents"].append(parent.id)

    def get_node(self, node_id: str) -> Optional[ProductionNode]:
        return self.all_nodes.get(node_id)

    def _reset_structure(self):
        """Restores all nodes to the captured initial structure."""
        if not self._initial_structure:
            return

        for node_id, node in self.all_nodes.items():
            node.parents.clear()
            node.children.clear()
            node.absorbed_by = None

            init = self._initial_structure.get(node_id)
            if init:
                for p_id in init["parents"]:
                    if p_id in self.all_nodes:
                        node.add_parent(self.all_nodes[p_id])
                for c_id in init["children"]:
                    if c_id in self.all_nodes:
                        node.add_child(self.all_nodes[c_id])

    def apply_merge(self, source_id: str, target_id: str):
        if source_id == target_id:
            return

        source = self.get_node(source_id)
        target = self.get_node(target_id)
        if not source or not target:
            return

        if source.output_item_name != target.output_item_name:
            raise ValueError(f"Cannot merge {source_id} and {target_id}: different output items")

        # A recipe switch upstream can make either node dormant; merging into a dormant
        # target would silently drop the source's demand, so the merge no longer applies.
        if source.is_dormant or target.is_dormant:
            return

        # Record merge. Each node keeps its own external demand; recalculate adds up the group's.
        self.merges[source_id] = target_id
        source.absorbed_by = target_id

        # Execute link transfer
        self._execute_merge_links(source, target)

    def _execute_merge_links(self, source: ProductionNode, target: ProductionNode):
        # Parents of source now point to target
        for parent in list(source.parents):
            if source in parent.children:
                parent.children.remove(source)
            parent.add_child(target)
            target.add_parent(parent)
            source.parents.discard(parent) # Clear link from source

        # Children of source now receive from target
        for child in list(source.children):
            if source in child.parents:
                child.parents.remove(source)
            child.add_parent(target)
            target.add_child(child)
            source.children.discard(child) # Clear link from source

    def set_subtree_dormancy(self, node_id: str, dormant: bool):
        """Makes a node and everything under it in the unmerged structure dormant (a dropped input) or active."""
        node = self.get_node(node_id)
        if node is None:
            return
        node.is_dormant = dormant
        for child in self._original_children(node):
            self.set_subtree_dormancy(child.id, dormant)

    def recalculate(self, round_up: bool = False):
        """
        Propagates demand top-down and sets every node's scale (see _propagate).

        A by-product loop the plan asks to solve (SOLVE) can't be ordered: its maker's output depends on
        the demand it covers. It is solved on fractional buildings, round by round: each round supplies
        what the maker made in the round before (none in the first). When the difference grows instead
        of shrinking, rounds take only part of the step (damping), so loops with strong feedback settle
        too. Whole buildings are then set in one more pass with the settled amounts; they make at least
        that much, the rest going to the Sink. If it doesn't settle in LOOP_ROUNDS, `loop_settled` is
        False and the plan is shown without those uses.
        """
        self.loop_settled, self.loop_rounds = True, 0
        self._propagate(round_up, {})
        if not self.byproduct_solving:
            return
        supply: Dict[Tuple[str, str], float] = {}
        damping, last = 1.0, math.inf
        for self.loop_rounds in range(1, LOOP_ROUNDS + 1):
            self._propagate(False, supply)
            made = {use: self._byproduct_made(*use) for use in self.byproduct_solving}
            residual = max(abs(rate - supply.get(use, 0.0)) for use, rate in made.items())
            if residual <= LOOP_TOLERANCE:
                self._propagate(round_up, supply)
                return
            if residual >= last:
                damping /= 2
            last = residual
            supply = {use: supply.get(use, 0.0) + damping * (rate - supply.get(use, 0.0)) for use, rate in made.items()}
        # Didn't settle: show the plan without these uses, so it adds up; their by-products go to the Sink
        self.loop_settled = False
        self._propagate(round_up, {})

    def _byproduct_made(self, maker_id: str, item: str) -> float:
        maker = self.all_nodes[maker_id]
        return sum(rate for i, rate in maker.recipe.other_outputs(maker.output_item_name) if i.name == item) \
            * maker.building_scale

    def _propagate(self, round_up: bool, loop_supply: Dict[Tuple[str, str], float]):
        """
        Propagates demand top-down and sets every node's scale.

        A merge group (a target and the nodes absorbed into it) runs as one set of buildings for the
        sum of its members' demands. Each member keeps its own input nodes, from the unmerged
        structure: for each input item, the group's need is split between the members' input nodes
        in proportion to each member's share of the group's demand. Members without an input node for
        an item (e.g. the group runs a different recipe) leave their share to the members that have one.

        Inbound production (`self.inbound`) covers demand before anything is produced: each group, top
        down, takes what it needs of its item until the inbound rate is used up, and makes only the rest.
        A group left with nothing to make, and everything under it that then needs nothing, goes into
        `self.unused` and isn't shown.

        By-products a node uses as supply (`byproduct_choice`) cover demand the same way, after inbound
        production. A maker is ordered before every group of its by-product, as its output depends on its
        own scale. A use whose ordering would close a loop (a consumer upstream of its own maker, directly
        or through other by-products) isn't applied: it goes into `self.byproduct_loops`, and the
        by-product goes to the Sink, unless the plan asks to solve it: then `loop_supply` (what its maker
        made in the round before, see recalculate) is there from the start.
        """
        active = {node_id: node for node_id, node in self.all_nodes.items() if not node.is_dormant}
        for node in active.values():
            self._external(node)  # record it before parent_demands is rebuilt below
        rep_of ={node_id: self._representative(node, active).id for node_id, node in active.items()}
        members: Dict[str, List[ProductionNode]] = {}
        for node_id, node in active.items():
            members.setdefault(rep_of[node_id], []).append(node)

        # Absorbed nodes don't run on their own
        for node_id, node in active.items():
            if rep_of[node_id] != node_id:
                node.original_building_scale = 0
                node.ideal_building_scale = 0
                node.set_clocks(None)
                node.parent_demands = {}

        # 2. Order groups top-down: an edge for every unmerged parent -> child link
        group_parents: Dict[str, Set[str]] = {rep_id: set() for rep_id in members}
        group_children: Dict[str, Set[str]] = {rep_id: set() for rep_id in members}
        for node_id, node in active.items():
            parent = self._original_parent(node)
            if parent is not None and parent.id in active and rep_of[parent.id] != rep_of[node_id]:
                group_parents[rep_of[node_id]].add(rep_of[parent.id])
                group_children[rep_of[parent.id]].add(rep_of[node_id])

        order_children = {rep_id: set(children) for rep_id, children in group_children.items()}
        uses = self._order_byproduct_uses(members, order_children)
        in_degree = {rep_id: 0 for rep_id in members}
        for children in order_children.values():
            for child_id in children:
                in_degree[child_id] += 1
        queue = [rep_id for rep_id, degree in in_degree.items() if degree == 0]
        demand: Dict[str, float] = {}  # per node (member), from its own parent or the user
        group_demand: Dict[str, float] = {}
        inbound_left = dict(self.inbound)
        self.inbound_used = {item: {} for item in self.inbound}
        self.unused = set()
        idle: Set[str] = set()
        byproducts_left: Dict[str, List[List]] = {}  # item -> [[maker id, rate left], ...], in the order made
        for maker_id, item in sorted(self.byproduct_solving):
            byproducts_left.setdefault(item, []).append([maker_id, loop_supply.get((maker_id, item), 0.0)])
        self.byproduct_used = {use: {} for use in uses + sorted(self.byproduct_solving)}

        def cover(rep: ProductionNode, need: float, amount: float, used: Dict[str, float]):
            """
            Moves `amount` of the group's remaining `need` from its consumers' demand to `used`. The user's
            own demand is recorded against the group itself, which stays shown (see below).
            """
            for consumer, rate in list(rep.parent_demands.items()):
                key = rep.id if consumer == "External Demand" else consumer
                used[key] = used.get(key, 0) + rate * amount / need
                rep.parent_demands[consumer] = rate * (1 - amount / need)

        def share(rep_id: str, member: ProductionNode) -> float:
            total = group_demand[rep_id]
            return demand[member.id] / total if total > 0 else 1 / len(members[rep_id])

        def member_demand(member: ProductionNode) -> Tuple[Optional[str], float]:
            """(parent group id or None, rate) demanded of this one node by its own parent."""
            parent = self._original_parent(member)
            if parent is None or parent.id not in active:
                return None, 0.0
            parent_rep = self.all_nodes[rep_of[parent.id]]
            need = sum(inp["rate"] for inp in parent_rep.scaled_inputs if inp["item"] == member.output_item_name)
            if need <= 0:
                return parent_rep.id, 0.0
            # Input nodes for this item under any member of the parent group, weighted by their parent's share
            suppliers = [
                child
                for parent_member in members[parent_rep.id]
                for child in self._original_children(parent_member)
                if child.id in active and child.output_item_name == member.output_item_name
            ]
            weights = {child.id: share(parent_rep.id, self._original_parent(child)) for child in suppliers}
            total = sum(weights.values())
            fraction = weights[member.id] / total if total > 0 else 1 / len(suppliers)
            return parent_rep.id, need * fraction

        while queue:
            rep_id = queue.pop(0)
            rep = self.all_nodes[rep_id]

            rep.parent_demands = {}
            total = 0.0
            for member in members[rep_id]:
                external = self._external(member)
                parent_id, rate = member_demand(member)
                demand[member.id] = external + rate
                total += external + rate
                if external > 0:
                    rep.parent_demands["External Demand"] = rep.parent_demands.get("External Demand", 0) + external
                if parent_id is not None and rate > 0:
                    rep.parent_demands[parent_id] = rep.parent_demands.get(parent_id, 0) + rate
            group_demand[rep_id] = total
            item = rep.output_item_name
            need = total
            if not rep.is_supplied:
                amount = min(need, inbound_left.get(item, 0.0))
                if amount > 0:
                    inbound_left[item] -= amount
                    cover(rep, need, amount, self.inbound_used[item])
                    need -= amount
                for entry in byproducts_left.get(item, []):
                    amount = min(need, entry[1])
                    if amount > EPSILON:
                        entry[1] -= amount
                        cover(rep, need, amount, self.byproduct_used[(entry[0], item)])
                        need -= amount
            rep.parent_demands = {k: v for k, v in rep.parent_demands.items() if v > EPSILON}
            self._set_scale(rep, need, round_up)
            # Idle: nothing left to make, as it's covered or everything above it is idle. Hidden, unless
            # the user demands it.
            if need <= EPSILON and (need < total or (group_parents[rep_id] and group_parents[rep_id] <= idle)):
                idle.add(rep_id)
                if not any(self._external(member) > 0 for member in members[rep_id]):
                    self.unused.add(rep_id)
            for (maker_id, byproduct) in uses:
                if maker_id == rep_id:
                    rate = dict((i.name, r) for i, r in rep.recipe.other_outputs(item))[byproduct]
                    byproducts_left.setdefault(byproduct, []).append([rep_id, rate * rep.building_scale])

            for child_id in order_children[rep_id]:
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0:
                    queue.append(child_id)

    def byproduct_choice(self, node_id: str) -> str:
        return self.byproduct_choices.get(node_id, self.byproduct_default)

    def _order_byproduct_uses(self, members: Dict[str, List[ProductionNode]],
                              order_children: Dict[str, Set[str]]) -> List[Tuple[str, str]]:
        """
        (maker id, item) for each by-product used as supply, after adding maker -> consumer group edges to
        `order_children`. A use whose edges would close a loop is left out and recorded in byproduct_loops,
        and also in byproduct_solving if the plan asks to solve it (SOLVE; a SOLVE without a loop is a plain USE).
        """
        self.byproduct_loops = set()
        self.byproduct_solving = set()
        groups_of: Dict[str, List[str]] = {}
        for rep_id in members:
            rep = self.all_nodes[rep_id]
            if not rep.is_supplied:
                groups_of.setdefault(rep.output_item_name, []).append(rep_id)

        def reaches(start: str, goal: str) -> bool:
            seen, stack = set(), [start]
            while stack:
                current = stack.pop()
                if current == goal:
                    return True
                if current not in seen:
                    seen.add(current)
                    stack.extend(order_children[current])
            return False

        uses = []
        for rep_id in sorted(members):
            rep = self.all_nodes[rep_id]
            if rep.recipe is None or self.byproduct_choice(rep_id) not in (USE, SOLVE):
                continue
            for item, _ in rep.recipe.other_outputs(rep.output_item_name):
                consumers = [group for group in groups_of.get(item.name, []) if group != rep_id]
                if any(reaches(consumer, rep_id) for consumer in consumers):
                    self.byproduct_loops.add((rep_id, item.name))
                    if self.byproduct_choice(rep_id) == SOLVE:
                        self.byproduct_solving.add((rep_id, item.name))
                    continue
                for consumer in consumers:
                    order_children[rep_id].add(consumer)
                uses.append((rep_id, item.name))
        return uses

    def _set_scale(self, node: ProductionNode, required_rate: float, round_up: bool):
        """
        With round_up, whole buildings: the fixed clock groups (e.g. the last building at 60%) plus as many
        buildings at the node's clock as the rest of the demand needs, rounded up. The count is never set
        directly; it follows the demand and the clocks (ticket 023). Without round_up, the exact fractional
        scale (used by tests to check that every item balances). A node supplied from outside has no
        buildings: its scale is just the rate it supplies.
        """
        if node.is_supplied:
            node.ideal_building_scale = node.original_building_scale = required_rate / node.base_output_rate
            node.set_clocks(None)
            return
        if node.base_output_rate <= 0:
            node.original_building_scale = 0
            node.ideal_building_scale = 0
            node.set_clocks([] if round_up else None)
            return
        base_scale = required_rate / node.base_output_rate
        node.ideal_building_scale = base_scale
        if not round_up:
            node.original_building_scale = base_scale
            node.set_clocks(None)
            return
        if base_scale <= 0:
            node.original_building_scale = 0
            node.set_clocks([])
            return
        rest_clock, fixed = self.clocks.get(node.id, (1.0, []))
        rest_scale = base_scale - sum(count * clock for count, clock in fixed)
        rest_count = max(0, math.ceil(rest_scale / rest_clock - 0.00001))
        groups = [(rest_count, rest_clock)] + fixed
        node.set_clocks(groups)
        node.original_building_scale = sum(count * clock for count, clock in groups)

    def _representative(self, node: ProductionNode, active: Dict[str, ProductionNode]) -> ProductionNode:
        """The merge target a node runs as (following chains of merges), or the node itself."""
        seen = {node.id}
        while node.absorbed_by and node.absorbed_by in active and node.absorbed_by not in seen:
            node = active[node.absorbed_by]
            seen.add(node.id)
        return node

    def _original_parent(self, node: ProductionNode) -> Optional[ProductionNode]:
        """The node's parent in the unmerged structure (the tree as built, plus recipe switches)."""
        parent_ids = self._initial_structure.get(node.id, {}).get("parents", [])
        return self.all_nodes.get(parent_ids[0]) if parent_ids else None

    def _original_children(self, node: ProductionNode) -> List[ProductionNode]:
        child_ids = self._initial_structure.get(node.id, {}).get("children", [])
        return [self.all_nodes[child_id] for child_id in child_ids if child_id in self.all_nodes]

    @staticmethod
    def _external(node: ProductionNode) -> float:
        """Rate the user asked of this node directly. Graphs wired by hand only set parent_demands."""
        if node.external_demand is None:
            node.external_demand = node.parent_demands.get("External Demand", 0)
        return node.external_demand

    def get_ui_data(self) -> List[Dict]:
        """
        Serialized nodes for the UI. A merge group is shown as its target alone: absorbed and dormant
        nodes are left out, links to absorbed nodes point to their target, and the target lists its
        absorbed nodes in `constituent_ids` / `constituent_derivations`. The target's scale and rates
        already cover the whole group (see recalculate).
        """
        ui_nodes = []
        target_to_constituents: Dict[str, List[ProductionNode]] = {}

        for node in self.all_nodes.values():
            if node.absorbed_by:
                target_id = node.absorbed_by
                if target_id not in target_to_constituents:
                    target_to_constituents[target_id] = []
                target_to_constituents[target_id].append(node)

        hidden = set(self.unused)
        for node in self.all_nodes.values():
            if node.absorbed_by or node.is_dormant or node.id in hidden:
                continue # Skip absorbed, dormant and unused nodes from top level

            constituents = [c for c in target_to_constituents.get(node.id, []) if not c.is_dormant]

            # Serialize representative
            data = self._serialize_node(node)

            # Map parents and children to their merge targets for UI consistency
            data["parents"] = sorted(list(set(
                self.get_node(p_id).absorbed_by or p_id
                for p_id in data["parents"]
                if p_id in self.all_nodes
            )))
            data["children"] = sorted(list(set(
                self.get_node(c_id).absorbed_by or c_id
                for c_id in data["children"]
                if c_id in self.all_nodes
            ) - hidden) + [INBOUND_PREFIX + item for item, used in self.inbound_used.items() if node.id in used])

            # Mark if it's a merged node and track constituents
            data["is_merged"] = len(constituents) > 0
            data["constituent_ids"] = [c.id for c in constituents]
            data["constituent_derivations"] = [self.derivation(c) for c in constituents]
            data["byproducts"] = self._byproducts_of(node)

            ui_nodes.append(data)

        sink = self._sink_node([data["id"] for data in ui_nodes])
        ui_nodes.extend(self._inbound_node(item) for item in self.inbound)
        if sink:
            ui_nodes.append(sink)
        return ui_nodes

    def _byproducts_of(self, node: ProductionNode) -> List[Dict]:
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
            "choice": self.byproduct_choice(node.id),
            "loop": (node.id, item.name) in self.byproduct_loops,
            "solving": (node.id, item.name) in self.byproduct_solving,
            "settled": self.loop_settled, "rounds": self.loop_rounds,
            "used": {k: v for k, v in self.byproduct_used.get((node.id, item.name), {}).items() if v > EPSILON},
        } for item, rate in node.recipe.other_outputs(node.output_item_name)]

    def resolved_byproduct_choices(self) -> Dict[str, str]:
        """
        The choice of every node that makes a by-product, where the plan sets it or the default is USE:
        the plan to keep. A default SINK isn't recorded, so a later Calculate (default USE) can still use it.
        """
        resolved = {}
        for node in self.all_nodes.values():
            if node.is_dormant or node.absorbed_by or node.recipe is None or node.is_supplied:
                continue
            if node.recipe.other_outputs(node.output_item_name):
                if node.id in self.byproduct_choices or self.byproduct_default == USE:
                    resolved[node.id] = self.byproduct_choice(node.id)
        return resolved

    def _sink_node(self, node_ids: List[str]) -> Optional[Dict]:
        """
        The Sink, in the shape of a serialized node, if any shown node has a by-product left after what is
        used as supply: `sink.inputs` lists each ({from, item, rate, fluid, loop}). Fluids can't be sunk; they
        are listed anyway, so the rest of the plan calculates, and `sink.fluids` flags them (ticket 024).
        """
        inputs = []
        for node_id in node_ids:
            for byproduct in self._byproducts_of(self.all_nodes[node_id]):
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

    def _inbound_node(self, item: str) -> Dict:
        """An item's inbound production, in the shape of a serialized node: it feeds the nodes that used it."""
        used = self.inbound_used.get(item, {})
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
            "inbound": {"rate": self.inbound[item], "used": total},
        }

    def derivation(self, node: ProductionNode) -> List[Dict]:
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
            ancestor = self.get_node(prefix)
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

    def _serialize_node(self, node: ProductionNode) -> Dict:
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
            "is_supplied": node.is_supplied,
            "derivation": self.derivation(node),
        }
