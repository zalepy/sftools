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

Each edge of the production graph is a number of belts (ticket 041): by default the fewest its rate
needs, or what the plan sets (`edges`, by `edge_key`). Each belt has an end on both sides: an exit on
the producer's output side and an entry on the consumer's input side, belt k being the same belt at both
ends. The sides are simulated together (`attach_logistics`): output sides push, input sides pull (ticket
042). An edge whose count the plan sets is matched belt by belt: what its exit gets is what the entry
brings. An edge with the default count is a bundle: its belts share what the producer sends over what the
consumer takes, as if balanced.
"""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sftools.domain.enums.item_categories import ItemCategory
from sftools.domain.models.factory_graph import NEGLIGIBLE

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
}  # buildings: one belt for each item; entries and exits: see _ports
MAX_BELTS = 12  # per edge
SHORT = 0.005  # a shortfall below this shows as 0.00/min: not warned about (e.g. a clock of 166.666% for 5/3)
COUPLING_ROUNDS = 60  # passes over the sides until the belts between them settle


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


def belts_for(rate: float, fluid: bool, settings: Settings, count: int) -> Dict:
    """`count` belts for a rate: {kind, count, tier}, the lowest tier that carries each one's share (the
    highest unlocked if none does: then `over` is set)."""
    tiers = PIPES[:settings.pipe_tier] if fluid else BELTS[:settings.belt_tier]
    share = rate / count
    tier = next((i for i, cap in enumerate(tiers, 1) if cap >= share - EPSILON), len(tiers))
    result = {"kind": "pipe" if fluid else "belt", "count": count, "tier": tier}
    if share > tiers[-1] + EPSILON:
        result["over"] = True
    return result


def edge_key(producer: str, consumer: str, item: str) -> str:
    """How the plan names an edge for its belt count: consumer 'External Demand' or 'sink' for those ends."""
    return f"{producer}>{consumer}|{item}"


def _end_id(prefix: str, other: str, item: str, belt: int) -> str:
    """An exit ('x') or entry ('e') for belt k of an edge: the first keeps the id of a single belt."""
    return f"{prefix}|{other}|{item}" + (f"|{belt}" if belt > 1 else "")


# --- The sides of a node, as the plan gives them ---

def _building_clocks(node: Dict) -> List[float]:
    return [group["clock"] for group in node.get("clocks") or [] for _ in range(group["count"])]


def side_specs(nodes: List[Dict], is_fluid) -> Dict[str, Dict]:
    """
    For each production node with buildings, its sides: {'<id>|out': spec, '<id>|in': spec}. A spec maps
    each item to {"sources": [...], "sinks": [...]}, buildings numbered from 1 in clock-group order:
    on the output side sources are buildings (id, rate) and sinks the edges out (consumer, rate, label,
    belts, edge key); on the input side sources are the edges in (supplier, rate, belts, edge key) and
    sinks the buildings (id, rate, None). Entries come from the graph's edges into the node; exits from
    its consumers, the user's demand, and its by-products (used elsewhere, or to the Sink). The number of
    belts of each edge is the producer's `edge_belts` (see attach_logistics); 1 without it.
    """
    def belts(node: Dict, consumer: str, byproduct: Optional[Dict] = None) -> int:
        edge_belts = (byproduct if byproduct is not None else node).get("edge_belts") or {}
        return (edge_belts.get(consumer) or {}).get("count", 1)

    entries: Dict[str, Dict[str, List[Tuple]]] = {}  # consumer -> item -> [(supplier, rate, belts, key)]
    for node in nodes:
        for consumer in node.get("parents", []):
            rate = (node.get("parent_demands") or {}).get(consumer, 0)
            if rate > EPSILON:
                item = node["output_item"]
                entries.setdefault(consumer, {}).setdefault(item, []).append(
                    (node["id"], rate, belts(node, consumer), edge_key(node["id"], consumer, item)))
        for byproduct in node.get("byproducts") or []:
            for consumer, rate in byproduct["used"].items():
                if rate > EPSILON:
                    item = byproduct["item"]
                    entries.setdefault(consumer, {}).setdefault(item, []).append(
                        (node["id"], rate, belts(node, consumer, byproduct), edge_key(node["id"], consumer, item)))

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
            "sinks": [(consumer, rate, "demand" if consumer == "External Demand" else consumer,
                       belts(node, consumer), edge_key(node["id"], consumer, main))
                      for consumer, rate in (node.get("parent_demands") or {}).items() if rate > EPSILON],
        }
        for byproduct in node.get("byproducts") or []:
            per_building = byproduct["rate"] / scale if scale else 0
            item = byproduct["item"]
            used = {k: v for k, v in byproduct["used"].items() if v > EPSILON}
            sinks = [(consumer, rate, consumer, belts(node, consumer, byproduct), edge_key(node["id"], consumer, item))
                     for consumer, rate in used.items()]
            left = byproduct["rate"] - sum(used.values())
            if left >= NEGLIGIBLE:
                sinks.append(("sink", left, "Sink", belts(node, "sink", byproduct), edge_key(node["id"], "sink", item)))
            out[byproduct["item"]] = {
                "sources": [(f"b{i}", per_building * clock) for i, clock in enumerate(clocks, 1)],
                "sinks": sinks,
            }
        specs[f"{node['id']}|out"] = {"node": node["id"], "side": "out", "items": out}

        inputs: Dict[str, Dict] = {}
        for base in node.get("base_inputs") or []:
            item = base["item"]
            inputs[item] = {
                "sources": entries.get(node["id"], {}).get(item, []),
                "sinks": [(f"b{i}", base["rate"] * clock, None) for i, clock in enumerate(clocks, 1)],
            }
        if inputs:
            specs[f"{node['id']}|in"] = {"node": node["id"], "side": "in", "items": inputs}
    return specs


def fixed_nodes(spec: Dict, settings: Settings, is_fluid) -> List[Dict]:
    """
    The nodes the plan gives a side: buildings, and entries (in) or exits (out), per item: one for each
    belt of an edge (`belt` k of `belts`), taking one belt. An exit's `rate` is the edge's (its belts share
    it); an entry's is its belt's share, until the producer's side says what the belt brings (simulate).
    """
    result = []
    for item, sub in spec["items"].items():
        if spec["side"] == "out":
            result += [{"id": f"{b}|{item}", "kind": BUILDING, "item": item, "rate": rate, "building": b}
                       for b, rate in sub["sources"]]
            result += [{"id": _end_id("x", target, item, k), "kind": EXIT, "item": item, "rate": rate, "target": target,
                        "label": label, "belt": k, "belts": count, "edge": key}
                       for target, rate, label, count, key in sub["sinks"] for k in range(1, count + 1)]
        else:
            result += [{"id": _end_id("e", source, item, k), "kind": ENTRY, "item": item, "rate": rate / count,
                        "total": rate, "target": source, "belt": k, "belts": count, "edge": key}
                       for source, rate, count, key in sub["sources"] for k in range(1, count + 1)]
            result += [{"id": f"{b}|{item}", "kind": BUILDING, "item": item, "rate": rate, "building": b}
                       for b, rate, _ in sub["sinks"]]
    return result


# --- Default layouts ---

class _Builder:
    def __init__(self):
        self.nodes: List[Dict] = []
        self.belts: List[Dict] = []
        self.count = 0
        self.mains: Dict[str, str] = {}  # smart splitter -> the exit prefix its main output leads to (_priority)

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

    def combine_to(self, sources: List[str], count: int, item: str) -> List[str]:
        """At most `count` nodes that carry all the sources: the first ones as they are, the rest merged."""
        if len(sources) <= count:
            return list(sources)
        return sources[:count - 1] + [self.combine(sources[count - 1:], item)]

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


def default_layout(spec: Dict, settings: Settings, is_fluid, matched: frozenset = frozenset(),
                   targets: Optional[Dict[Tuple[str, int], float]] = None) -> Dict:
    """
    Output side: buildings grouped by destination. Each edge gets whole buildings while they fit its
    rate; the buildings left over are merged and split over the edges still short. Surplus backs up (the
    buildings idle part of the time). An edge of several belts gets its sources spread over them: up to
    `targets` ({(edge key, belt): rate}, what the consumer's side takes on each), or evenly.
    Input side: the entries merged onto one belt per belt-load of buildings, each feeding a manifold. The
    belts of a `matched` edge (and of one whose belts each carry a building's need or more) each feed
    their own buildings, in order.
    """
    fixed = fixed_nodes(spec, settings, is_fluid)
    builder = _Builder()
    for item, sub in spec["items"].items():
        capacity = settings.capacity(is_fluid(item))
        if spec["side"] == "out":
            buildings = sorted(((f"{b}|{item}", rate) for b, rate in sub["sources"]), key=lambda b: -b[1])
            edges = sorted(sub["sinks"], key=lambda e: -e[1])
            feeds: Dict[str, List[Tuple[str, float]]] = {e[0]: [] for e in edges}  # (source, rate) for each edge
            short = []
            for target, rate, *_ in edges:
                total = 0.0
                for building in list(buildings):
                    if total + building[1] <= rate + EPSILON:
                        feeds[target].append(building)
                        total += building[1]
                        buildings.remove(building)
                if rate - total > EPSILON:
                    short.append((target, rate - total))
            if buildings and short:
                # With smart splitters, edges that get no whole building are filled first (they take just
                # what they miss); the rest is shared evenly by the others, which take more than they miss
                # when their buildings' belts merge with it
                missing = dict(short)
                empty = sorted((t for t, _ in short if not feeds[t]), key=lambda t: -missing[t])
                others = [t for t, _ in short if feeds[t]]
                for chunk in _chunks(buildings, capacity):
                    source = builder.combine([b for b, _ in chunk], item)
                    if settings.smart and empty and len(short) > 1:
                        pairs = _priority(builder, source, empty, others, item)
                    else:
                        pairs = _fan_out(builder, source, empty + others, item)
                    for target, node in pairs:
                        feeds[target].append((node, missing[target]))
            elif buildings and edges:
                feeds[edges[0][0]] += buildings  # surplus: onto the largest edge, where it backs up
            for target, rate, _, count, key in edges:
                shares = [(targets or {}).get((key, k)) for k in range(1, count + 1)]
                if None in shares:
                    shares = [rate / count] * count
                loads = _spread(builder, feeds[target], shares, item) if count > 1 else [feeds[target]]
                for belt, load in enumerate(loads, 1):
                    if load:
                        builder.belt(builder.combine([source for source, _ in load], item), _end_id("x", target, item, belt))
        else:
            entries = [(_end_id("e", source, item, k), rate / count)
                       for source, rate, count, _ in sub["sources"] for k in range(1, count + 1)]
            buildings = [(f"{b}|{item}", rate) for b, rate, _ in sub["sinks"]]
            chosen = any(key in matched and count > 1 for _, _, count, key in sub["sources"])
            whole = len(entries) > len(sub["sources"]) and min(r for _, r in entries) >= max(r for _, r in buildings) - EPSILON
            if chosen or whole:
                _belt_shares(builder, entries, buildings, item)
            elif entries:
                _input_lines(builder, entries, buildings, item, capacity)
    # A smart splitter's main output is the one toward its edge; the others take the overflow
    for splitter, prefix in builder.mains.items():
        for belt in builder.belts:
            if belt["from"] == splitter:
                belt["overflow"] = not _reaches(builder.belts, belt["to"], prefix)
    return {"fixed": sorted(node["id"] for node in fixed), "nodes": builder.nodes, "belts": builder.belts}


def _reaches(belts: List[Dict], node: str, prefix: str) -> bool:
    """Whether belts from `node` lead to an exit of the edge `prefix` ('x|<target>|<item>', any belt)."""
    if node == prefix or node.startswith(prefix + "|"):
        return True
    return any(_reaches(belts, b["to"], prefix) for b in belts if b["from"] == node)


def _priority(builder: "_Builder", source: str, firsts: List[str], rest: List[str], item: str) -> List[Tuple[str, str]]:
    """
    Source to `firsts` in order, through a chain of smart (overflow) splitters, each filling its target
    first and passing the overflow on; what's left is split evenly over `rest`. [(target, node that feeds it)].
    """
    result, current = [], source
    for index, target in enumerate(firsts):
        if index == len(firsts) - 1 and not rest:
            return result + [(target, current)]
        splitter = builder.part(OVERFLOW, item)
        builder.belt(current, splitter)
        builder.mains[splitter] = f"x|{target}|{item}"
        result.append((target, splitter))
        current = splitter
    return result + _fan_out(builder, current, rest, item)


def _input_lines(builder: "_Builder", entries: List[Tuple[str, float]], buildings: List[Tuple[str, float]],
                 item: str, capacity: float):
    """
    Entries onto belts, each feeding a manifold. On one belt if it carries them all: the merger then takes
    exactly what each entry brings. Otherwise the buildings are grouped into belt-loads, and entries are
    given to the groups in order, an entry split (with a splitter) over two groups where needed. A merger
    shares evenly between inputs that both back up, so such a split can leave a building short (a warning
    shows); the user can rework it.
    """
    if sum(rate for _, rate in entries) <= capacity + EPSILON:
        builder.split(builder.combine([e for e, _ in entries], item), [b for b, _ in buildings], item)
        return
    chunks = _chunks(buildings, capacity)
    left = [rate for _, rate in entries]  # what each entry has left to give
    feeds: List[List[int]] = []  # for each chunk, the entries feeding it
    for chunk in chunks:
        need = sum(rate for _, rate in chunk)
        feeds.append([])
        for index in range(len(entries)):  # until the chunk's need is covered
            if need <= EPSILON:
                break
            if left[index] > EPSILON:
                feeds[-1].append(index)
                taken = min(left[index], need)
                left[index] -= taken
                need -= taken
        if not feeds[-1]:
            feeds[-1].append(len(entries) - 1)
    for index in range(len(entries)):  # more than the buildings need: with the last group, where it backs up
        if not any(index in feed for feed in feeds):
            feeds[-1].append(index)
    sources: Dict[Tuple[int, int], str] = {}  # (entry, chunk) -> what brings the entry's share to the chunk
    for index, (entry_id, _) in enumerate(entries):
        for chunk, source in _fan_out(builder, entry_id, [c for c, feed in enumerate(feeds) if index in feed], item):
            sources[(index, chunk)] = source
    for chunk, feed in enumerate(feeds):
        builder.split(builder.combine([sources[(index, chunk)] for index in feed], item), [b for b, _ in chunks[chunk]], item)


def _spread(builder: "_Builder", sources: List[Tuple[str, float]], shares: List[float],
            item: str) -> List[List[Tuple[str, float]]]:
    """
    Sources over the belts of an edge, each up to its share: whole ones, largest first onto the belt with
    the most room that takes them; the ones left merged and split evenly over the belts still short (or
    onto the one with the most room).
    """
    count = len(shares)
    loads: List[List[Tuple[str, float]]] = [[] for _ in range(count)]
    totals = [0.0] * count
    left = []
    for source in sorted(sources, key=lambda s: -s[1]):
        room = [shares[i] - totals[i] for i in range(count)]
        belt = room.index(max(room))
        if source[1] <= room[belt] + EPSILON:
            loads[belt].append(source)
            totals[belt] += source[1]
        else:
            left.append(source)
    if left:
        room = [shares[i] - totals[i] for i in range(count)]
        short = [i for i in range(count) if room[i] > EPSILON] or [room.index(max(room))]
        merged = builder.combine([s for s, _ in left], item)
        for belt, node in _fan_out(builder, merged, short, item):
            loads[belt].append((node, 0.0))
    return loads


def _belt_shares(builder: "_Builder", entries: List[Tuple[str, float]], buildings: List[Tuple[str, float]], item: str):
    """
    Edges of several belts: the buildings in order, each fed by the belt whose share of the supply covers
    the middle of its need (e.g. three belts of 9 to buildings needing 10, 10 and 7: one each). A belt that
    covers no building's middle joins the belt before it (or after, for the first).
    """
    bounds, total = [], 0.0
    for _, rate in entries:
        bounds.append((total, total + rate))
        total += rate
    groups: List[List[str]] = [[] for _ in entries]
    need = 0.0
    for building, rate in buildings:
        middle = need + rate / 2
        need += rate
        index = next((i for i, (lo, hi) in enumerate(bounds) if lo - EPSILON <= middle < hi), len(entries) - 1)
        groups[index].append(building)
    feeders: Dict[int, List[str]] = {}  # first entry of each group of buildings -> the entries feeding it
    owner = None
    for index, (entry, _) in enumerate(entries):
        if groups[index]:
            owner = index
            feeders[index] = feeders.pop(-1, []) + [entry]
        elif owner is None:
            feeders.setdefault(-1, []).append(entry)  # before the first group: joins it
        else:
            feeders[owner].append(entry)
    for index, sources in feeders.items():
        if index >= 0:
            builder.split(builder.combine(sources, item), groups[index], item)


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
    if node["kind"] == EXIT:  # one belt each (ticket 041)
        return 1, 0
    if node["kind"] == ENTRY:
        return 0, 1
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


def _fair(total: float, offers: List[float]) -> List[float]:
    """
    How much each of several inputs may send when they share `total` fairly: the level where the offers,
    each cut at it, add up to `total`. When all the offers fit, each may send its offer and the room left.
    """
    if total == math.inf:
        return [math.inf] * len(offers)
    left = total
    for i, offer in enumerate(sorted(offers)):
        share = left / (len(offers) - i)
        if offer >= share:
            return [share] * len(offers)
        left -= offer
    return [offer + left for offer in offers]


def simulate(layout: Dict, spec: Dict, settings: Settings, is_fluid, supply: Optional[Dict] = None) -> Dict:
    """
    Steady-state flows: sources (buildings out, entries in) push their rate; mergers share what their
    output takes among their inputs, an overflow splitter fills its main outputs first.

    An input side is pulled: splitters share evenly among the outputs that aren't backed up, and its
    buildings take up to their rate (a buffer takes anything). An output side is pushed (ticket 042): its
    buildings put out all they make, splitters share it evenly among the outputs whose belts have room,
    and exits take all they get, which shows how the layout splits it. Only an overflow splitter's main
    outputs back up short of that, once the exits they reach have their edge's rate (the exits of one
    edge share it). Repeated until the flows stop changing.

    `supply` ({(edge key, belt): rate}) is what each entry's belt brings, from its exit (attach_logistics).
    """
    side = spec["side"]
    push = side == "out"
    supply = supply or {}
    nodes = {node["id"]: dict(node) for node in fixed_nodes(spec, settings, is_fluid)}
    for node in nodes.values():
        if node["kind"] == ENTRY and (node.get("edge"), node.get("belt")) in supply:
            node["rate"] = supply[(node["edge"], node["belt"])]
    pools: Dict[str, List[str]] = {}  # edge key -> its exits
    for node_id, node in nodes.items():
        if node["kind"] == EXIT:
            pools.setdefault(node["edge"], []).append(node_id)
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
    accept = {b["id"]: b["capacity"] for b in belts}  # what each belt can take, the sinks taking their rate
    room = {b["id"]: b["capacity"] for b in belts}  # the same, every sink taking all it gets (push)
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
            spaces = [room[b["id"]] for b in out] if push else limits
            if kind == OVERFLOW:
                main = [i for i, b in enumerate(out) if not b.get("overflow")]
                extra = [i for i, b in enumerate(out) if b.get("overflow")]
                shares = [0.0] * len(out)
                for i, share in zip(main, _water_fill(inflow, [limits[i] for i in main])):
                    shares[i] = share
                left = inflow - sum(shares)
                for i, share in zip(extra, _water_fill(left, [spaces[i] for i in extra])):
                    shares[i] = share
                left = inflow - sum(shares)
                if push and left > EPSILON:  # the overflow is full too: the main outputs take what they have room for
                    for i, share in zip(main, _water_fill(left, [spaces[i] - shares[i] for i in main])):
                        shares[i] += share
            else:
                shares = _water_fill(inflow, spaces)
            for belt, share in zip(out, shares):
                flow[belt["id"]] = share
        # What each belt can take, from the end back. Inputs share it fairly: one that carries less than it
        # may (all its supply) keeps that, and the rest is split evenly among those that would send more.
        def offer(belt, takes):
            return belt["capacity"] if flow[belt["id"]] >= takes[belt["id"]] - EPSILON else flow[belt["id"]]

        def back(takes, sink_total):
            for node_id in reversed(order):
                node = nodes[node_id]
                total = sink_total(node) if role(node) == "sink" else sum(takes[b["id"]] for b in outs[node_id])
                into = ins[node_id]
                for belt, share in zip(into, _fair(total, [offer(b, takes) for b in into])):
                    takes[belt["id"]] = min(belt["capacity"], share)

        shared = {}  # each exit's share of its edge's rate
        for members in pools.values():
            into = [(b, m) for m in members for b in ins[m]]
            for (belt, member), share in zip(into, _fair(nodes[members[0]]["rate"], [offer(b, accept) for b, m in into])):
                shared[member] = shared.get(member, 0.0) + share
        back(accept, lambda node: shared.get(node["id"], 0.0) if node["kind"] == EXIT
             else math.inf if node["kind"] == BUFFER else node["rate"])
        if push:
            back(room, lambda node: math.inf)
        if all(abs(flow[k] - previous[k]) <= EPSILON for k in flow):
            break

    warnings = []
    for members in pools.values():
        delivered = sum(nodes[m]["in"] for m in members)
        for m in members:
            nodes[m]["pool_delivered"] = delivered
        if delivered < nodes[members[0]]["rate"] - SHORT:
            first = {**nodes[members[0]], "belts": 1}
            warnings.append(f"{_name(first)} gets {delivered:.2f} of {first['rate']:.2f}/min")
    for node_id, node in nodes.items():
        kind = role(node)
        if node["kind"] == EXIT:
            node["delivered"] = node["in"]
            if not ins[node_id]:
                warnings.append(f"{_name(node)} isn't connected")
        elif kind == "sink" and node["kind"] != BUFFER:
            node["delivered"] = min(node["in"], node["rate"])
            if node["delivered"] < node["rate"] - SHORT:
                warnings.append(f"{_name(node)} gets {node['delivered']:.2f} of {node['rate']:.2f}/min")
            if not ins[node_id]:
                warnings.append(f"{_name(node)} isn't connected")
        elif kind == "source":
            node["sent"] = sum(flow[b["id"]] for b in outs[node_id])
            if node["kind"] == ENTRY:  # what the side would take on this belt: limits the producer's exit
                node["accepts"] = sum(accept[b["id"]] for b in outs[node_id])
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
        "complexity": _complexity(nodes, ins, outs),
        "warnings": warnings,
        "backed_up": max(0.0, backed_up),
    }


def _complexity(nodes: Dict[str, Dict], ins: Dict[str, List], outs: Dict[str, List]) -> int:
    """Splitters and mergers."""
    return sum(1 for node in nodes.values() if node["kind"] in (SPLITTER, MERGER, OVERFLOW))


def _name(node: Dict) -> str:
    if node["kind"] == BUILDING:
        return f"Building {node['building'][1:]}"
    belt = f" (belt {node['belt']}/{node['belts']})" if node.get("belts", 1) > 1 else ""
    if node["kind"] == EXIT:
        return (f"Exit to {node['label']}" if node["label"] != "demand" else "The demand") + belt
    if node["kind"] == ENTRY:
        return f"Entry from {node['target']}{belt}"
    return node["id"]


def attach_logistics(nodes: List[Dict], is_fluid, settings: Settings, layouts: Dict[str, Dict],
                     edges: Optional[Dict[str, int]] = None) -> List[Dict]:
    """
    Adds `logistics: {in, out}` to every production node with buildings: each side's layout (the plan's,
    or the default), its flows and warnings, and whether it was edited. Returns the plan's layouts that
    no longer fit, which are reset: [{key, reason}].

    `edges` sets the number of belts of an edge (by edge_key); others get the fewest their rate needs.
    """
    counts = {}
    for key, count in (edges or {}).items():
        try:
            counts[key] = min(max(int(count), 1), MAX_BELTS)
        except (TypeError, ValueError):
            pass

    needs: Dict[str, int] = {}  # edge key -> the fewest belts its rate needs

    def belts(producer: str, consumer: str, item: str, rate: float) -> Dict:
        fluid = is_fluid(item)
        needed = belts_needed(rate, fluid, settings)["count"]
        key = edge_key(producer, consumer, item)
        needs[key] = needed
        return {**belts_for(rate, fluid, settings, counts.get(key, needed)), "needed": needed, "key": key}

    # The production graph's edges (tickets 028, 041): belts or pipes for each, by tier and count
    for node in nodes:
        if node.get("sink"):
            continue
        node["edge_belts"] = {consumer: belts(node["id"], consumer, node["output_item"], rate)
                              for consumer, rate in (node.get("parent_demands") or {}).items() if rate > EPSILON}
        for byproduct in node.get("byproducts") or []:
            rates = {consumer: rate for consumer, rate in byproduct["used"].items() if rate > EPSILON}
            left = byproduct["rate"] - sum(rates.values())
            if left >= NEGLIGIBLE:
                rates["sink"] = left
            byproduct["edge_belts"] = {consumer: belts(node["id"], consumer, byproduct["item"], rate)
                                       for consumer, rate in rates.items()}

    resets = []
    specs = side_specs(nodes, is_fluid)
    by_id = {node["id"]: node for node in nodes}
    for key, layout in (layouts or {}).items():
        if key not in specs:
            resets.append({"key": key, "reason": "the node isn't in the plan any more"})
    # Edges with both ends: matched belt by belt when the plan sets their count, else bundled
    exits, entries = set(), set()
    for spec in specs.values():
        for item, sub in spec["items"].items():
            if spec["side"] == "out":
                exits.update(e[4] for e in sub["sinks"])
            else:
                entries.update(e[3] for e in sub["sources"])
    linked = exits & entries
    matched = frozenset(key for key in linked if key in counts)

    chosen = {}  # key -> (layout, edited); defaults after: the output sides follow the input sides
    for key, spec in specs.items():
        layout = (layouts or {}).get(key)
        edited = layout is not None
        if edited:
            reason = validate(layout, spec, settings, is_fluid)
            if reason:
                resets.append({"key": key, "reason": reason})
                layout, edited = None, False
        if layout is not None:
            chosen[key] = (layout, edited)
    targets: Dict[Tuple[str, int], float] = {}  # what each matched belt's input side takes
    for key, spec in specs.items():
        if spec["side"] == "in":
            if key not in chosen:
                chosen[key] = (default_layout(spec, settings, is_fluid, matched), False)
            for node in simulate(chosen[key][0], spec, settings, is_fluid)["nodes"]:
                if node["kind"] == ENTRY and node["edge"] in matched:
                    targets[(node["edge"], node["belt"])] = node["accepts"]
    for key, spec in specs.items():
        if key not in chosen:
            chosen[key] = (default_layout(spec, settings, is_fluid, matched, targets), False)

    # The belts between two sides (ticket 042): the output sides push, so they come first; each entry then
    # brings what its exit gets (a bundle: what its exits get together, over the entries as they take it,
    # any more evenly, up to what a belt carries). Repeated over the input sides until what the bundles'
    # entries take settles.
    results = {key: simulate(layout, specs[key], settings, is_fluid)
               for key, (layout, _) in chosen.items() if specs[key]["side"] == "out"}
    sent: Dict[str, Dict[int, float]] = {}  # edge -> belt -> what its exit gets
    for result in results.values():
        for node in result["nodes"]:
            if node["kind"] == EXIT and node["edge"] in linked:
                sent.setdefault(node["edge"], {})[node["belt"]] = node["delivered"]
    supply: Dict[Tuple[str, int], float] = {(edge, belt): rate for edge in matched for belt, rate in sent[edge].items()}
    taken: Dict[str, Dict[int, float]] = {}  # edge -> belt -> what its entry lets through
    for _ in range(COUPLING_ROUNDS):
        new_supply = dict(supply)
        for edge in linked - matched:
            belts = sorted(taken.get(edge) or sent[edge])
            total = sum(sent[edge].values())
            shares = _water_fill(total, [taken[edge][b] for b in belts] if edge in taken else [math.inf] * len(belts))
            capacity = settings.capacity(is_fluid(edge.rsplit("|", 1)[1]))
            more = _water_fill(total - sum(shares), [capacity - share for share in shares])
            new_supply.update({(edge, belt): share + extra for belt, share, extra in zip(belts, shares, more)})
        if taken and _close(new_supply, supply):
            break
        supply = new_supply
        inputs = {key: simulate(layout, specs[key], settings, is_fluid, supply)
                  for key, (layout, _) in chosen.items() if specs[key]["side"] == "in"}
        taken = {}
        for result in inputs.values():
            for node in result["nodes"]:
                if node["kind"] == ENTRY and node["edge"] in linked:
                    taken.setdefault(node["edge"], {})[node["belt"]] = node["accepts"]
    for result in results.values():  # what a matched belt's entry takes, shown on its exit
        for node in result["nodes"]:
            if node["kind"] == EXIT and node["edge"] in matched:
                node["limit"] = taken[node["edge"]][node["belt"]]
    results.update(inputs)

    for key, result in results.items():
        layout, edited = chosen[key]
        spec = specs[key]
        for node in result["nodes"]:  # belt ends: the edge's default count, and whether the plan sets it
            if node.get("edge"):
                node.update({"needed": needs.get(node["edge"], 1), "set": node["edge"] in counts})
        result.update({"key": key, "side": spec["side"], "edited": edited, "fixed": layout["fixed"]})
        by_id[spec["node"]].setdefault("logistics", {})[spec["side"]] = result
    return resets


def _close(a: Dict, b: Dict) -> bool:
    return a.keys() == b.keys() and all(abs(a[k] - b[k]) <= EPSILON for k in a)
