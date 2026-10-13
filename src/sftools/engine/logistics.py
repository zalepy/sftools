"""
Logistics mode (ticket 033): how items get from buildings to buildings.

Each production node has two logistics sides: `in` (from the belts that bring its inputs to its
buildings) and `out` (from its buildings to the belts that leave it, one per outgoing edge). A side is
a small network of buildings, splitters, mergers and belts, with one sub-network per item. The tool
builds a default for each side (`default_layout`); the user can edit it, and the plan then keeps the
edited layout. `simulate` computes the steady-state flow on every belt.

Layouts are stored by key '<node id>|in' / '<node id>|out' as {"fixed": [ids], "nodes": [{id, kind,
item}], "belts": [{from, to, overflow}]}. `fixed` lists the nodes the plan gives the side (buildings,
entries, exits): when they change (e.g. a building more), the stored layout no longer fits and is reset
to the default.
"""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sftools.domain.enums.item_categories import ItemCategory

BELTS = [60, 120, 270, 480, 780, 1200]  # items/min, Mk.1-6
PIPES = [300, 600]  # m³/min, Mk.1-2
FLUIDS = {ItemCategory.LIQUIDS, ItemCategory.GAS}
EPSILON = 1e-6
MAX_ROUNDS = 500

# Node kinds. Roles: buildings are sources on the output side and sinks on the input side.
BUILDING, ENTRY, EXIT, BUFFER = "building", "entry", "exit", "buffer"
SPLITTER, MERGER, OVERFLOW = "splitter", "merger", "overflow"
PARTS = (SPLITTER, MERGER, OVERFLOW, BUFFER)  # what the user can add
PORTS = {  # (max belts in, max belts out); None: any number
    SPLITTER: (1, 3), OVERFLOW: (1, 3), MERGER: (3, 1), BUFFER: (None, 0),
}  # buildings: one belt for each item; entries and exits: as many as their rate needs (see _ports)


@dataclass
class Settings:
    belt_tier: int = 6  # highest belt unlocked
    pipe_tier: int = 2
    smart: bool = True  # smart/programmable splitters unlocked

    @classmethod
    def parse(cls, data: Optional[Dict]) -> "Settings":
        data = data or {}
        return cls(
            belt_tier=min(max(int(data.get("belt_tier", 6)), 1), len(BELTS)),
            pipe_tier=min(max(int(data.get("pipe_tier", 2)), 1), len(PIPES)),
            smart=bool(data.get("smart", True)),
        )

    def capacity(self, fluid: bool) -> float:
        return PIPES[self.pipe_tier - 1] if fluid else BELTS[self.belt_tier - 1]


def belts_needed(rate: float, fluid: bool, settings: Settings) -> Dict:
    """How a rate travels: {kind: belt|pipe, count, tier}: the fewest belts of the highest tier unlocked,
    then the lowest tier that carries each one's share."""
    tiers = PIPES[:settings.pipe_tier] if fluid else BELTS[:settings.belt_tier]
    count = max(1, math.ceil(rate / tiers[-1] - EPSILON))
    share = rate / count
    tier = next(i for i, cap in enumerate(tiers, 1) if cap >= share - EPSILON)
    return {"kind": "pipe" if fluid else "belt", "count": count, "tier": tier}


# --- The sides of a node, as the plan gives them ---

def _building_clocks(node: Dict) -> List[float]:
    return [group["clock"] for group in node.get("clocks") or [] for _ in range(group["count"])]


def side_specs(nodes: List[Dict], is_fluid) -> Dict[str, Dict]:
    """
    For each production node with buildings, its sides: {'<id>|out': spec, '<id>|in': spec}. A spec maps
    each item to {"sources": [(id, rate)], "sinks": [(id, rate, label)]}, buildings numbered from 1 in
    clock-group order. Entries come from the graph's edges into the node; exits from its consumers, the
    user's demand, and its by-products (used elsewhere, or to the Sink).
    """
    by_id = {node["id"]: node for node in nodes}
    entries: Dict[str, Dict[str, List[Tuple[str, float]]]] = {}  # consumer -> item -> [(supplier, rate)]
    for node in nodes:
        for consumer in node.get("parents", []):
            rate = (node.get("parent_demands") or {}).get(consumer, 0)
            if rate > EPSILON:
                entries.setdefault(consumer, {}).setdefault(node["output_item"], []).append((node["id"], rate))
        for byproduct in node.get("byproducts") or []:
            for consumer, rate in byproduct["used"].items():
                if rate > EPSILON:
                    entries.setdefault(consumer, {}).setdefault(byproduct["item"], []).append((node["id"], rate))

    specs = {}
    for node in nodes:
        clocks = _building_clocks(node)
        if not clocks or node.get("is_supplied") or node.get("inbound") or node.get("sink"):
            continue
        scale = sum(clocks)
        out: Dict[str, Dict] = {}
        main = node["output_item"]
        out[main] = {
            "sources": [(f"b{i}", node["base_output_rate"] * clock) for i, clock in enumerate(clocks, 1)],
            "sinks": [(consumer, rate, "demand" if consumer == "External Demand" else consumer)
                      for consumer, rate in (node.get("parent_demands") or {}).items() if rate > EPSILON],
        }
        for byproduct in node.get("byproducts") or []:
            per_building = byproduct["rate"] / scale if scale else 0
            used = {k: v for k, v in byproduct["used"].items() if v > EPSILON}
            sinks = [(consumer, rate, consumer) for consumer, rate in used.items()]
            left = byproduct["rate"] - sum(used.values())
            if left > EPSILON:
                sinks.append(("sink", left, "Sink"))
            out[byproduct["item"]] = {
                "sources": [(f"b{i}", per_building * clock) for i, clock in enumerate(clocks, 1)],
                "sinks": sinks,
            }
        specs[f"{node['id']}|out"] = {"node": node["id"], "side": "out", "items": out}

        inputs: Dict[str, Dict] = {}
        for base in node.get("base_inputs") or []:
            item = base["item"]
            inputs[item] = {
                "sources": [(supplier, rate) for supplier, rate in entries.get(node["id"], {}).get(item, [])],
                "sinks": [(f"b{i}", base["rate"] * clock, None) for i, clock in enumerate(clocks, 1)],
            }
        if inputs:
            specs[f"{node['id']}|in"] = {"node": node["id"], "side": "in", "items": inputs}
    return specs


def fixed_nodes(spec: Dict, settings: Settings, is_fluid) -> List[Dict]:
    """
    The nodes the plan gives a side: buildings, and entries (in) or exits (out), per item. An entry or
    exit is an edge of the production graph: `lines` is how many belts it takes (see belts_needed).
    """
    result = []
    for item, sub in spec["items"].items():
        def lines(rate):
            return belts_needed(rate, is_fluid(item), settings)["count"]
        if spec["side"] == "out":
            result += [{"id": f"{b}|{item}", "kind": BUILDING, "item": item, "rate": rate, "building": b}
                       for b, rate in sub["sources"]]
            result += [{"id": f"x|{target}|{item}", "kind": EXIT, "item": item, "rate": rate, "target": target,
                        "label": label, "lines": lines(rate)} for target, rate, label in sub["sinks"]]
        else:
            result += [{"id": f"e|{source}|{item}", "kind": ENTRY, "item": item, "rate": rate, "target": source,
                        "lines": lines(rate)} for source, rate in sub["sources"]]
            result += [{"id": f"{b}|{item}", "kind": BUILDING, "item": item, "rate": rate, "building": b}
                       for b, rate, _ in sub["sinks"]]
    return result


# --- Default layouts ---

class _Builder:
    def __init__(self):
        self.nodes: List[Dict] = []
        self.belts: List[Dict] = []
        self.count = 0

    def part(self, kind: str, item: str) -> str:
        self.count += 1
        node_id = f"{kind[0]}{self.count}"
        self.nodes.append({"id": node_id, "kind": kind, "item": item})
        return node_id

    def belt(self, source: str, target: str, overflow: bool = False):
        # An overflow splitter's first output is its main one; the others take the overflow
        if any(n["id"] == source and n["kind"] == OVERFLOW for n in self.nodes):
            overflow = any(b["from"] == source for b in self.belts)
        self.belts.append({"from": source, "to": target, "overflow": overflow})

    def combine(self, sources: List[str], item: str) -> str:
        """
        The node whose output carries all the sources: a chain of mergers (3 inputs each) if several. A
        merger of ours that has no output yet and a free input takes more sources first.
        """
        if len(sources) == 1:
            return sources[0]
        first, sources = sources[0], list(sources[1:])
        if self._open_merger(first):
            while sources and sum(1 for b in self.belts if b["to"] == first) < 3:
                self.belt(sources.pop(0), first)
            if not sources:
                return first
        sources = [first] + sources
        current = self.part(MERGER, item)
        for source in sources[:3]:
            self.belt(source, current)
        rest = sources[3:]
        while rest:
            following = self.part(MERGER, item)
            self.belt(current, following)
            for source in rest[:2]:
                self.belt(source, following)
            rest, current = rest[2:], following
        return current

    def _open_merger(self, node_id: str) -> bool:
        return any(n["id"] == node_id and n["kind"] == MERGER for n in self.nodes) and             not any(b["from"] == node_id for b in self.belts)

    def merge(self, sources: List[str], target: str, item: str):
        self.belt(self.combine(sources, item), target)

    def split(self, source: str, targets: List[str], item: str):
        """Source to targets, through a chain of splitters when there are several (a manifold)."""
        if len(targets) == 1:
            self.belt(source, targets[0])
            return
        current = source
        for index, target in enumerate(targets[:-1]):
            splitter = self.part(SPLITTER, item)
            self.belt(current, splitter)
            self.belt(splitter, target)
            if index == len(targets) - 2:
                self.belt(splitter, targets[-1])
            current = splitter


def _chunks(entries: List[Tuple[str, float]], capacity: float) -> List[List[Tuple[str, float]]]:
    """Consecutive groups whose rates add up to at most `capacity` (one belt each)."""
    chunks, current, total = [], [], 0.0
    for entry in entries:
        if current and total + entry[1] > capacity + EPSILON:
            chunks.append(current)
            current, total = [], 0.0
        current.append(entry)
        total += entry[1]
    if current:
        chunks.append(current)
    return chunks


def default_layout(spec: Dict, settings: Settings, is_fluid) -> Dict:
    """
    Output side: buildings grouped by destination. Each exit gets whole buildings while they fit its
    rate (merged, one belt per belt-load); the buildings left over are merged and split over the exits
    still short. Surplus backs up (the buildings idle part of the time).
    Input side: the entries merged onto one belt per belt-load of buildings, each feeding a manifold.
    """
    fixed = fixed_nodes(spec, settings, is_fluid)
    builder = _Builder()
    for item, sub in spec["items"].items():
        capacity = settings.capacity(is_fluid(item))
        if spec["side"] == "out":
            buildings = sorted(((f"{b}|{item}", rate) for b, rate in sub["sources"]), key=lambda b: -b[1])
            exits = sorted(((f"x|{target}|{item}", rate) for target, rate, _ in sub["sinks"]), key=lambda e: -e[1])
            feeds: Dict[str, List[str]] = {exit_id: [] for exit_id, _ in exits}  # what each exit's belts take
            short = []
            for exit_id, rate in exits:
                group, total = [], 0.0
                for building in list(buildings):
                    if total + building[1] <= rate + EPSILON:
                        group.append(building)
                        total += building[1]
                        buildings.remove(building)
                for chunk in _chunks(group, capacity):
                    feeds[exit_id].append(builder.combine([b for b, _ in chunk], item))
                if rate - total > EPSILON:
                    short.append(exit_id)
            if buildings and short:
                for chunk in _chunks(buildings, capacity):
                    for exit_id, source in _fan_out(builder, builder.combine([b for b, _ in chunk], item), short, item):
                        feeds[exit_id].append(source)
            elif buildings and exits:
                for chunk in _chunks(buildings, capacity):  # surplus: onto the largest exit, where it backs up
                    feeds[exits[0][0]].append(builder.combine([b for b, _ in chunk], item))
            for exit_id, rate in exits:  # one belt per belt-load of the exit's rate
                lines = belts_needed(rate, is_fluid(item), settings)["count"]
                sources = feeds[exit_id]
                for line in range(min(lines, len(sources))):
                    builder.belt(builder.combine(sources[line::lines], item), exit_id)
        else:
            entries = [(f"e|{source}|{item}", rate) for source, rate in sub["sources"]]
            buildings = [(f"{b}|{item}", rate) for b, rate, _ in sub["sinks"]]
            if entries:
                _input_lines(builder, entries, buildings, item, capacity)
    return {"fixed": sorted(node["id"] for node in fixed), "nodes": builder.nodes, "belts": builder.belts}


def _input_lines(builder: "_Builder", entries: List[Tuple[str, float]], buildings: List[Tuple[str, float]],
                 item: str, capacity: float):
    """
    Entries onto belts, each feeding a manifold. On one belt if it carries them all: the merger then takes
    exactly what each entry brings. Otherwise the buildings are grouped into belt-loads, and entries are
    given to the groups in order, an entry split over two groups where needed. A merger shares evenly
    between inputs that both back up, so such a split can leave a building short (a warning shows); the
    user can rework it.
    """
    if sum(rate for _, rate in entries) <= capacity + EPSILON:
        builder.split(builder.combine([e for e, _ in entries], item), [b for b, _ in buildings], item)
        return
    left = [rate for _, rate in entries]  # what each entry has left to give
    for chunk in _chunks(buildings, capacity):
        need = sum(rate for _, rate in chunk)
        feeds = []
        for index, (entry_id, _) in enumerate(entries):  # until the chunk's need is covered
            if need <= EPSILON:
                break
            if left[index] > EPSILON:
                feeds.append(entry_id)
                taken = min(left[index], need)
                left[index] -= taken
                need -= taken
        if not feeds:
            feeds = [entries[-1][0]]
        builder.split(builder.combine(feeds, item), [b for b, _ in chunk], item)


def _fan_out(builder: _Builder, source: str, targets: List[str], item: str) -> List[Tuple[str, str]]:
    """Source split over the targets with a splitter (3 outputs) chain: [(target, node that feeds it)]."""
    if len(targets) == 1:
        return [(targets[0], source)]
    result, current, rest = [], source, list(targets)
    while rest:
        splitter = builder.part(SPLITTER, item)
        builder.belt(current, splitter)
        if len(rest) <= 3:
            return result + [(target, splitter) for target in rest]
        result += [(target, splitter) for target in rest[:2]]
        rest, current = rest[2:], splitter
    return result


# --- Validation and simulation ---

def validate(layout: Dict, spec: Dict, settings: Settings, is_fluid) -> Optional[str]:
    """Why a layout can't be used for the side (None if it can): stale fixed nodes, bad belts, ports, loops."""
    fixed = {node["id"]: node for node in fixed_nodes(spec, settings, is_fluid)}
    if sorted(layout.get("fixed", [])) != sorted(fixed):
        return "the node's buildings or edges changed"
    nodes = dict(fixed)
    for node in layout.get("nodes", []):
        if node.get("kind") not in PARTS or node.get("id") in nodes:
            return f"bad part {node.get('id')!r}"
        nodes[node["id"]] = node
    ins: Dict[str, int] = {}
    outs: Dict[str, int] = {}
    for belt in layout.get("belts", []):
        source, target = nodes.get(belt.get("from")), nodes.get(belt.get("to"))
        if source is None or target is None:
            return "a belt to an unknown node"
        if source["item"] != target["item"]:
            return "a belt between different items"
        outs[source["id"]] = outs.get(source["id"], 0) + 1
        ins[target["id"]] = ins.get(target["id"], 0) + 1
    for node_id, node in nodes.items():
        max_in, max_out = _ports(node, spec["side"])
        if max_in is not None and ins.get(node_id, 0) > max_in:
            return f"too many belts into {node_id}"
        if max_out is not None and outs.get(node_id, 0) > max_out:
            return f"too many belts out of {node_id}"
    if _order(nodes, layout.get("belts", [])) is None:
        return "a loop (only trees for now)"
    return None


def _ports(node: Dict, side: str) -> Tuple[Optional[int], Optional[int]]:
    if node["kind"] == BUILDING:  # one port for the item
        return (0, 1) if side == "out" else (1, 0)
    if node["kind"] == EXIT:
        return node["lines"], 0
    if node["kind"] == ENTRY:
        return 0, node["lines"]
    return PORTS[node["kind"]]


def _order(nodes: Dict[str, Dict], belts: List[Dict]) -> Optional[List[str]]:
    """Node ids in belt order (Kahn), or None if the belts loop."""
    degree = {node_id: 0 for node_id in nodes}
    following: Dict[str, List[str]] = {node_id: [] for node_id in nodes}
    for belt in belts:
        degree[belt["to"]] += 1
        following[belt["from"]].append(belt["to"])
    queue = sorted(node_id for node_id, d in degree.items() if d == 0)
    order = []
    while queue:
        node_id = queue.pop(0)
        order.append(node_id)
        for target in following[node_id]:
            degree[target] -= 1
            if degree[target] == 0:
                queue.append(target)
    return order if len(order) == len(nodes) else None


def _water_fill(amount: float, limits: List[float]) -> List[float]:
    """Equal shares of `amount`, each up to its limit; what a full one can't take goes to the others."""
    shares = [0.0] * len(limits)
    open_ = [i for i in range(len(limits))]
    while amount > EPSILON and open_:
        share = amount / len(open_)
        full = [i for i in open_ if limits[i] - shares[i] <= share + EPSILON]
        if not full:
            for i in open_:
                shares[i] += share
            return shares
        for i in full:
            amount -= limits[i] - shares[i]
            shares[i] = limits[i]
        open_ = [i for i in open_ if i not in full]
    return shares


def simulate(layout: Dict, spec: Dict, settings: Settings, is_fluid) -> Dict:
    """
    Steady-state flows: sources (buildings out, entries in) push their rate; splitters share evenly among
    the outputs that aren't backed up, mergers share what their output takes among their inputs, an
    overflow splitter fills its main outputs first. Sinks take up to their rate (a buffer takes anything).
    Repeated until the flows stop changing.
    """
    side = spec["side"]
    nodes = {node["id"]: dict(node) for node in fixed_nodes(spec, settings, is_fluid)}
    for node in layout["nodes"]:
        nodes[node["id"]] = {**node}
    belts = [{**belt, "id": f"{belt['from']}>{belt['to']}"} for belt in layout["belts"]]
    for belt in belts:
        belt["capacity"] = settings.capacity(is_fluid(nodes[belt["from"]]["item"]))
    ins = {node_id: [b for b in belts if b["to"] == node_id] for node_id in nodes}
    outs = {node_id: [b for b in belts if b["from"] == node_id] for node_id in nodes}
    order = _order(nodes, belts)

    def role(node):
        if node["kind"] == BUILDING:
            return "source" if side == "out" else "sink"
        return {ENTRY: "source", EXIT: "sink", BUFFER: "sink"}.get(node["kind"], node["kind"])

    flow = {b["id"]: 0.0 for b in belts}
    accept = {b["id"]: b["capacity"] for b in belts}
    for _ in range(MAX_ROUNDS):
        previous = dict(flow)
        for node_id in order:
            node = nodes[node_id]
            kind = role(node)
            inflow = node["rate"] if kind == "source" else sum(flow[b["id"]] for b in ins[node_id])
            node["in"] = inflow
            if kind == "sink":
                continue
            out = outs[node_id]
            limits = [accept[b["id"]] for b in out]
            if kind == OVERFLOW:
                main = [i for i, b in enumerate(out) if not b.get("overflow")]
                extra = [i for i, b in enumerate(out) if b.get("overflow")]
                shares = [0.0] * len(out)
                for i, share in zip(main, _water_fill(inflow, [limits[i] for i in main])):
                    shares[i] = share
                left = inflow - sum(shares)
                for i, share in zip(extra, _water_fill(left, [limits[i] for i in extra])):
                    shares[i] = share
            else:
                shares = _water_fill(inflow, limits)
            for belt, share in zip(out, shares):
                flow[belt["id"]] = share
        for node_id in reversed(order):  # what each belt can take, from the end back
            node = nodes[node_id]
            kind = role(node)
            if kind == "sink":
                total = math.inf if node["kind"] == BUFFER else node["rate"]
            else:
                total = sum(accept[b["id"]] for b in outs[node_id])
            into = ins[node_id]
            for belt in into:
                others = sum(flow[b["id"]] for b in into if b is not belt)
                accept[belt["id"]] = min(belt["capacity"], max(total / len(into), total - others))
        if all(abs(flow[k] - previous[k]) <= EPSILON for k in flow):
            break

    warnings = []
    for node_id, node in nodes.items():
        kind = role(node)
        if kind == "sink" and node["kind"] != BUFFER:
            node["delivered"] = min(node["in"], node["rate"])
            if node["delivered"] < node["rate"] - 1e-4:
                warnings.append(f"{_name(node)} gets {node['delivered']:.2f} of {node['rate']:.2f}/min")
            if not ins[node_id]:
                warnings.append(f"{_name(node)} isn't connected")
        elif kind == "source":
            node["sent"] = sum(flow[b["id"]] for b in outs[node_id])
            if not outs[node_id]:
                warnings.append(f"{_name(node)} isn't connected")
            elif node["kind"] == BUILDING and node["rate"] > outs[node_id][0]["capacity"] + EPSILON:
                warnings.append(f"{_name(node)} makes {node['rate']:.2f}/min, more than one "
                                f"{'pipe' if is_fluid(node['item']) else 'belt'} carries")
    for belt in belts:
        belt["flow"] = flow[belt["id"]]
        belt["tier"] = belts_needed(belt["flow"], is_fluid(nodes[belt["from"]]["item"]), settings)["tier"]
        belt["full"] = belt["flow"] >= belt["capacity"] - EPSILON
    backed_up = sum(n["rate"] - n.get("sent", 0) for n in nodes.values() if role(n) == "source")
    return {
        "nodes": list(nodes.values()),
        "belts": belts,
        "complexity": sum(1 for n in nodes.values() if n["kind"] in (SPLITTER, MERGER, OVERFLOW)),
        "warnings": warnings,
        "backed_up": max(0.0, backed_up),
    }


def _name(node: Dict) -> str:
    if node["kind"] == BUILDING:
        return f"Building {node['building'][1:]}"
    if node["kind"] == EXIT:
        return f"Exit to {node['label']}" if node["label"] != "demand" else "The demand"
    if node["kind"] == ENTRY:
        return f"Entry from {node['target']}"
    return node["id"]


def attach_logistics(nodes: List[Dict], is_fluid, settings: Settings, layouts: Dict[str, Dict]) -> List[Dict]:
    """
    Adds `logistics: {in, out}` to every production node with buildings: each side's layout (the plan's,
    or the default), its flows and warnings, and whether it was edited. Returns the plan's layouts that
    no longer fit, which are reset: [{key, reason}].
    """
    # The production graph's edges (ticket 028): belts or pipes for each, by tier and count
    for node in nodes:
        if node.get("sink"):
            continue
        fluid = is_fluid(node["output_item"])
        node["edge_belts"] = {consumer: belts_needed(rate, fluid, settings)
                              for consumer, rate in (node.get("parent_demands") or {}).items() if rate > EPSILON}
        for byproduct in node.get("byproducts") or []:
            fluid = is_fluid(byproduct["item"])
            rates = {consumer: rate for consumer, rate in byproduct["used"].items() if rate > EPSILON}
            left = byproduct["rate"] - sum(rates.values())
            if left > EPSILON:
                rates["sink"] = left
            byproduct["edge_belts"] = {consumer: belts_needed(rate, fluid, settings) for consumer, rate in rates.items()}

    resets = []
    specs = side_specs(nodes, is_fluid)
    by_id = {node["id"]: node for node in nodes}
    for key, layout in (layouts or {}).items():
        if key not in specs:
            resets.append({"key": key, "reason": "the node isn't in the plan any more"})
    for key, spec in specs.items():
        layout = (layouts or {}).get(key)
        edited = layout is not None
        if edited:
            reason = validate(layout, spec, settings, is_fluid)
            if reason:
                resets.append({"key": key, "reason": reason})
                layout, edited = None, False
        if layout is None:
            layout = default_layout(spec, settings, is_fluid)
        result = simulate(layout, spec, settings, is_fluid)
        result.update({"key": key, "side": spec["side"], "edited": edited, "fixed": layout["fixed"]})
        by_id[spec["node"]].setdefault("logistics", {})[spec["side"]] = result
    return resets
