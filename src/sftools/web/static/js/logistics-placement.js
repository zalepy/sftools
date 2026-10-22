// Where the nodes of the zoomed-in logistics view go: no DOM, so it's unit-tested (tests/js/).
// Sources in the left column, sinks in the right one, parts in columns between by belt order.

const COLUMN = 230;
const ROW = 72;

/**
 * Where each node of one side goes ({id: {x, y}}): where the user put it, else in its column (sources,
 * parts by belt order, sinks). `saved`: the user's positions.
 */
export function placement({ nodes, belts }, side, saved = {}) {
    const isSource = n => n.kind === 'entry' || (n.kind === 'building' && side === 'out');
    const isSink = n => n.kind === 'exit' || (n.kind === 'building' && side === 'in');
    const before = {}, after = {};
    belts.forEach(b => {
        (before[b.to] = before[b.to] || []).push(b.from);
        (after[b.from] = after[b.from] || []).push(b.to);
    });

    // Columns: parts one further than the furthest part feeding them
    const rank = {};
    const rankOf = (id, seen = new Set()) => {
        if (rank[id] !== undefined) return rank[id];
        if (seen.has(id)) return 1;
        seen.add(id);
        const node = nodes.find(n => n.id === id);
        if (!node || isSource(node)) return (rank[id] = 0);
        const feeding = (before[id] || []).filter(other => !isSink(nodes.find(n => n.id === other) || {}));
        return (rank[id] = 1 + Math.max(0, ...feeding.map(other => rankOf(other, seen))));
    };
    const parts = nodes.filter(n => !isSource(n) && !isSink(n));
    parts.forEach(n => rankOf(n.id));
    const last = Math.max(0, ...parts.map(n => rank[n.id])) + 1;

    const positions = {};
    const order = (a, b) => a.id.localeCompare(b.id, undefined, { numeric: true });
    nodes.filter(isSource).sort(order).forEach((n, i) => { positions[n.id] = { x: 0, y: i * ROW }; });
    Object.assign(positions, pick(saved, nodes.filter(isSource)));

    // Sinks face what feeds them, through any parts, so belts cross as little as they can
    const sourceY = (id, seen = new Set()) => {
        if (positions[id] && nodes.find(n => n.id === id && isSource(n))) return [positions[id].y];
        if (seen.has(id)) return [];
        seen.add(id);
        return (before[id] || []).flatMap(other => sourceY(other, seen));
    };
    const mean = values => values.reduce((s, v) => s + v, 0) / values.length;
    const sinks = nodes.filter(isSink).map(n => ({ n, y: sourceY(n.id) })).map(({ n, y }) => ({ n, y: y.length ? mean(y) : Infinity }));
    if (side === 'in') {
        // Buildings in order, each with its inputs together
        const building = n => parseInt(n.building.slice(1), 10);
        sinks.sort((a, b) => building(a.n) - building(b.n) || a.n.item.localeCompare(b.n.item));
        sinks.forEach((s, i) => { positions[s.n.id] = { x: last * COLUMN, y: i * ROW }; });
    } else {
        sinks.sort((a, b) => byY(a.y, b.y) || order(a.n, b.n));
        spread(sinks.map(s => ({ id: s.n.id, y: s.y === Infinity ? null : s.y })), last * COLUMN, positions);
    }
    Object.assign(positions, pick(saved, nodes.filter(isSink)));

    // Parts at the mean height of what they connect to; new ones, with no belts yet, below the others
    for (let column = 1; column < last; column++) {
        const placed = parts.filter(n => rank[n.id] === column).map(n => {
            const near = [...(before[n.id] || []), ...(after[n.id] || [])].filter(id => positions[id]).map(id => positions[id].y);
            return { id: n.id, y: near.length ? mean(near) : null };
        });
        placed.sort((a, b) => byY(a.y ?? Infinity, b.y ?? Infinity));
        spread(placed, column * COLUMN, positions);
    }
    Object.assign(positions, pick(saved, parts));
    return positions;
}

function byY(a, b) {
    return a === b ? 0 : a < b ? -1 : 1;
}

/** Positions in one column at x: each at its wanted y (null: after the others), kept a row apart. */
function spread(entries, x, positions) {
    let lowest = -Infinity;
    entries.forEach(({ id, y }) => {
        const placed = y === null ? (lowest === -Infinity ? 0 : lowest + ROW) : Math.max(y, lowest + ROW);
        positions[id] = { x, y: placed };
        lowest = placed;
    });
}

function pick(saved, nodes) {
    return Object.fromEntries(nodes.filter(n => saved[n.id]).map(n => [n.id, { ...saved[n.id] }]));
}
