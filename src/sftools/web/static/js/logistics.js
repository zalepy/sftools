// Logistics mode (ticket 033): the zoomed-in view of one logistics node, the input or output side of a
// production node. Its buildings, entries/exits, splitters, mergers and buffers are nodes here, and its
// belts edges. Drag a node to move it; drag from one of the dots under a node (its free outputs) to lay a
// belt; drag an end of a selected belt to move it (ticket 036). Every change is checked here first, then
// sent as the side's layout; the server simulates the flows (engine/logistics.py).
import { state } from './state.js';
import { textColorOn } from './graph.js';
import { showToast as toast } from './panel.js';

const $ = id => document.getElementById(id);

const PREFIX = { splitter: 's', merger: 'm', overflow: 'o', buffer: 'u' };
const PORTS = { splitter: [1, 3], overflow: [1, 3], merger: [3, 1], buffer: [null, 0] };  // [in, out]; null: any
const JOIN = 3;  // an exit merges up to 3 belts per line, an entry splits each line into up to 3 (engine JOIN)
const PART_LABELS = { splitter: 'Splitter', merger: 'Merger', overflow: 'Smart Splitter', buffer: 'Buffer' };
const EPSILON = 1e-4;

// Placement: sources in the left column, sinks in the right one, parts in columns between by belt order
const COLUMN = 230;
const ROW = 72;
const DOT = 14;  // between port dots

let lcy = null;
let view = null;  // { node, side, data, onChange, onMove, describe }
let drag = null;  // a belt being laid or moved: { from } or { belt, end: 'from' | 'to' }

function createGraph() {
    lcy = cytoscape({
        container: $('lcy'),
        boxSelectionEnabled: false,
        style: [
            {
                selector: 'node',
                style: {
                    'label': 'data(label)', 'text-wrap': 'wrap', 'text-valign': 'center', 'text-halign': 'center',
                    'font-size': '11px', 'color': '#f8fafc', 'width': 130, 'height': 46, 'shape': 'round-rectangle',
                    'background-color': '#334155', 'border-width': 2, 'border-color': '#64748b'
                }
            },
            { selector: '.building', style: { 'background-color': 'data(color)', 'color': 'data(textColor)', 'border-color': '#f59e0b' } },
            { selector: '.entry, .exit', style: { 'shape': 'tag', 'background-color': '#0f172a', 'border-color': '#38bdf8', 'width': 200, 'height': 56, 'text-max-width': 170 } },
            { selector: '.part', style: { 'shape': 'diamond', 'width': 54, 'height': 54, 'font-size': '9px', 'background-color': '#475569' } },
            { selector: '.merger', style: { 'shape': 'rectangle', 'width': 44, 'height': 44 } },
            { selector: '.buffer', style: { 'shape': 'barrel', 'width': 70 } },
            // Runs at another clock than the node's other buildings
            { selector: '.building.odd', style: { 'border-color': '#22d3ee', 'border-width': 4 } },
            { selector: '.short', style: { 'border-color': '#ef4444', 'border-width': 4 } },
            {
                selector: 'edge',
                style: {
                    'width': 3, 'line-color': '#64748b', 'target-arrow-color': '#64748b', 'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier', 'label': 'data(label)', 'font-size': '10px', 'color': '#cbd5e1',
                    'text-background-opacity': 1, 'text-background-color': '#0f172a', 'text-background-padding': '2px'
                }
            },
            { selector: 'edge.full', style: { 'line-color': '#f59e0b', 'target-arrow-color': '#f59e0b' } },
            { selector: 'edge.overflow', style: { 'line-style': 'dashed' } },
            { selector: ':selected', style: { 'border-color': '#f43f5e', 'border-width': 4, 'line-color': '#f43f5e', 'target-arrow-color': '#f43f5e' } },
            // A free output: drag from it to lay a belt
            {
                selector: '.handle',
                style: { 'shape': 'ellipse', 'width': 10, 'height': 10, 'label': '', 'background-color': '#38bdf8', 'border-width': 1, 'border-color': '#0f172a', 'z-index': 10 }
            },
            // An end of the selected belt: drag it to another node to move the belt
            {
                selector: '.end',
                style: { 'shape': 'ellipse', 'width': 14, 'height': 14, 'label': '', 'background-color': '#f43f5e', 'border-width': 2, 'border-color': '#f8fafc', 'z-index': 10 }
            },
            // While a belt is dragged: where it can go, and where it can't
            { selector: '.ok', style: { 'border-color': '#22c55e', 'border-width': 4 } },
            { selector: '.no', style: { 'opacity': 0.35 } },
            { selector: '.ghost', style: { 'width': 1, 'height': 1, 'opacity': 0, 'label': '' } },
            { selector: 'edge.ghost', style: { 'opacity': 0.7, 'line-style': 'dotted', 'label': '' } }
        ],
        minZoom: 0.1,
        maxZoom: 4
    });

    lcy.on('tapstart', 'node.handle', evt => startDrag({ from: evt.target.data('owner') }, evt.target.position()));
    lcy.on('tapstart', 'node.end', evt => {
        const end = evt.target.data('end');
        const belt = lcy.getElementById(evt.target.data('belt'));
        const fixedEnd = end === 'to' ? belt.source() : belt.target();
        startDrag({ belt: { from: belt.source().id(), to: belt.target().id() }, end }, fixedEnd.position());
    });
    lcy.on('tapdrag', evt => {
        if (drag) lcy.getElementById('__ghost').position({ ...evt.position });
    });
    lcy.on('tapend', evt => {
        if (drag) endDrag(evt.position);
    });
    lcy.on('select unselect', () => {
        updateButtons();
        showEnds();
    });
    // Port dots and belt ends follow their node; a node put somewhere is remembered
    lcy.on('position', 'node.real', evt => placeDots(evt.target));
    lcy.on('dragfree', 'node.real', () => {
        rememberPositions();
        view.onMove();
    });
}

/**
 * Opens the zoomed-in view. `describe(id)` names a production node; `onChange(layout|null)` applies an edit;
 * `onMove()` saves the plan after a node was moved.
 */
export function openView(node, side, onChange, describe, onMove) {
    view = { node, side, data: node.logistics[side], onChange, onMove, describe };
    $('logistics-view').hidden = false;
    if (!lcy) createGraph();
    lcy.resize();
    render(true);
}

/** Shows the side again after the plan was recalculated; closes the view if it's gone. */
export function refreshView(node) {
    if (!view) return;
    if (!node || !node.logistics || !node.logistics[view.side]) {
        closeView();
        return;
    }
    view.node = node;
    view.data = node.logistics[view.side];
    render(false);
}

export function closeView() {
    view = null;
    $('logistics-view').hidden = true;
}

export function isOpen() {
    return view !== null;
}

/** Which side is open: {nodeId, side}, or null. */
export function current() {
    return view && { nodeId: view.node.id, side: view.side };
}

function key() {
    return `${view.node.id}|${view.side}`;
}

function label(node) {
    const rate = value => `${parseFloat(value).toFixed(2)}/m`;
    const item = itemsOf().length > 1 ? `\n${node.item}` : '';
    switch (node.kind) {
        case 'building': {
            const flow = view.side === 'out' ? node.sent : node.delivered;
            return `${view.node.building} ${node.building.slice(1)}${item}\n${rate(flow)} of ${rate(node.rate)}`;
        }
        case 'entry':
            return `from ${view.describe(node.target)}${item}\n${rate(node.rate)}`;
        case 'exit': {
            const to = node.label === 'demand' ? 'the demand' : node.label === 'Sink' ? 'the Sink' : view.describe(node.target);
            return `to ${to}${item}\n${rate(node.delivered)} of ${rate(node.rate)}`;
        }
        case 'buffer':
            return `Buffer\n${rate(node.in || 0)}`;
        default:
            return PART_LABELS[node.kind];
    }
}

function itemsOf() {
    return [...new Set(view.data.nodes.map(n => n.item))];
}

function render(fit) {
    const data = view.data;
    const sideName = view.side === 'out' ? 'Output' : 'Input';
    $('lv-title').textContent = `${sideName} logistics: ${view.describe(view.node.id)}`;
    const items = itemsOf();
    const select = $('lv-item');
    const previous = select.value;
    select.replaceChildren(...items.map(item => new Option(item, item, false, item === previous)));
    select.hidden = items.length < 2;
    $('lv-add-overflow').disabled = !state.logistics.settings.smart;
    $('lv-warnings').replaceChildren(...data.warnings.map(text => Object.assign(document.createElement('li'), { textContent: text })));
    lcy.resize();  // the warnings above it change the graph's height

    const selected = lcy.$(':selected').map(e => e.id());
    const positions = placement();
    const odd = oddBuildings();
    const elements = data.nodes.map(node => {
        const color = state.colors[node.item] || '#334155';
        const short = node.delivered !== undefined && node.delivered < node.rate - EPSILON;
        return {
            group: 'nodes',
            data: { id: node.id, label: label(node), raw: node, color, textColor: textColorOn(color) },
            position: positions[node.id],
            classes: ['real', node.kind, PART_LABELS[node.kind] && node.kind !== 'buffer' && 'part',
                odd.has(node.building) && 'odd', short && 'short'].filter(Boolean)
        };
    });
    data.belts.forEach(belt => {
        elements.push({
            group: 'edges',
            data: {
                id: belt.id, source: belt.from, target: belt.to, raw: belt,
                label: `${belt.flow.toFixed(2)}/m · Mk.${belt.tier}${belt.overflow ? ' (overflow)' : ''}`
            },
            classes: [belt.full && 'full', belt.overflow && 'overflow'].filter(Boolean)
        });
    });
    lcy.elements().remove();
    lcy.add(elements);
    addDots();
    // Edited sides keep where everything is, so an edit doesn't move the rest around
    if (data.edited || state.logistics.positions[key()]) rememberPositions();
    selected.forEach(id => lcy.getElementById(id).select());
    if (fit) lcy.fit(undefined, 30);
    updateButtons();
    showEnds();
}

/** The buildings ('b3', ...) that run at another clock than most of the node's: buildings are numbered in clock-group order. */
function oddBuildings() {
    const clocks = (view.node.clocks || []).flatMap(group => Array(group.count).fill(group.clock));
    const counts = {};
    clocks.forEach(clock => { counts[clock] = (counts[clock] || 0) + 1; });
    const usual = Object.keys(counts).reduce((a, b) => (counts[b] > counts[a] ? b : a), clocks[0]);
    return new Set(clocks.map((clock, i) => String(clock) !== String(usual) && `b${i + 1}`).filter(Boolean));
}

// --- Placement ---

/** Where each node goes: where the user put it, else in its column (sources, parts by belt order, sinks). */
function placement() {
    const nodes = view.data.nodes;
    const saved = state.logistics.positions[key()] || {};
    const isSource = n => n.kind === 'entry' || (n.kind === 'building' && view.side === 'out');
    const isSink = n => n.kind === 'exit' || (n.kind === 'building' && view.side === 'in');
    const before = {}, after = {};
    view.data.belts.forEach(b => {
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
    if (view.side === 'in') {
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

/** Keeps where every node is, in the plan (saved with it). */
function rememberPositions() {
    const positions = {};
    lcy.nodes('.real').forEach(node => {
        const { x, y } = node.position();
        positions[node.id()] = { x: Math.round(x), y: Math.round(y) };
    });
    state.logistics.positions[key()] = positions;
}

// --- Port dots and belt ends ---

function ports(node) {
    if (node.kind === 'building') return view.side === 'out' ? [0, 1] : [1, 0];
    if (node.kind === 'exit') return [node.lines * JOIN, 0];
    if (node.kind === 'entry') return [0, node.lines * JOIN];
    return PORTS[node.kind];
}

/** One dot under each node for each free output. */
function addDots() {
    const dots = [];
    lcy.nodes('.real').forEach(node => {
        const raw = node.data('raw');
        const free = (ports(raw)[1] || 0) - node.outgoers('edge').length;
        for (let i = 0; i < free; i++) {
            dots.push({ group: 'nodes', data: { id: `__dot|${node.id()}|${i}`, owner: node.id(), index: i, count: free },
                classes: 'handle', selectable: false, grabbable: false });
        }
    });
    lcy.add(dots);
    lcy.nodes('.real').forEach(placeDots);
}

function placeDots(node) {
    const { x, y } = node.position();
    const bottom = y + node.outerHeight() / 2;
    lcy.nodes('.handle').filter(dot => dot.data('owner') === node.id()).forEach(dot => {
        dot.position({ x: x + (dot.data('index') - (dot.data('count') - 1) / 2) * DOT, y: bottom });
    });
    const belt = lcy.$('edge:selected')[0];
    if (belt && (belt.source().id() === node.id() || belt.target().id() === node.id())) placeEnds(belt);
}

/** Handles at both ends of the selected belt. */
function showEnds() {
    if (!lcy) return;
    lcy.remove('.end');
    const belt = lcy.$('edge:selected')[0];
    if (!belt || lcy.$(':selected').length > 1) return;
    lcy.add(['from', 'to'].map(end => ({ group: 'nodes', data: { id: `__end|${end}`, end, belt: belt.id() }, classes: 'end', selectable: false, grabbable: false })));
    placeEnds(belt);
}

function placeEnds(belt) {
    lcy.getElementById('__end|from').position({ ...belt.sourceEndpoint() });
    lcy.getElementById('__end|to').position({ ...belt.targetEndpoint() });
}

// --- Laying and moving belts ---

/** The layout with this drag dropped on `target`, or null if it changes nothing. */
function dropped(target) {
    const layout = currentLayout();
    if (drag.from) {
        if (target === drag.from || layout.belts.some(b => b.from === drag.from && b.to === target)) return null;
        layout.belts.push({ from: drag.from, to: target, overflow: takesOverflow(layout, drag.from) });
        return layout;
    }
    const index = layout.belts.findIndex(b => b.from === drag.belt.from && b.to === drag.belt.to);
    const belt = { ...layout.belts[index], [drag.end]: target };
    if (belt.from === belt.to || belt[drag.end] === drag.belt[drag.end]) return null;
    if (layout.belts.some(b => b.from === belt.from && b.to === belt.to)) return null;
    layout.belts.splice(index, 1);
    if (drag.end === 'from') belt.overflow = takesOverflow(layout, belt.from);
    layout.belts.splice(index, 0, belt);
    return layout;
}

// A smart splitter's first output is its main one; later ones take the overflow
function takesOverflow(layout, source) {
    const node = view.data.nodes.find(n => n.id === source);
    return Boolean(node && node.kind === 'overflow' && layout.belts.some(b => b.from === source));
}

function startDrag(what, anchor) {
    drag = what;
    lcy.userPanningEnabled(false);
    lcy.autoungrabify(true);
    lcy.add([
        { group: 'nodes', data: { id: '__ghost' }, position: { ...anchor }, classes: 'ghost' },
        { group: 'nodes', data: { id: '__anchor' }, position: { ...anchor }, classes: 'ghost' },
        { group: 'edges', data: { id: '__ghost_edge', source: '__anchor', target: '__ghost' }, classes: 'ghost' }
    ]);
    // Show where the belt can go
    lcy.nodes('.real').forEach(node => {
        const layout = dropped(node.id());
        node.addClass(layout && !problem(layout) ? 'ok' : 'no');
    });
}

function endDrag(position) {
    lcy.remove('.ghost');
    lcy.nodes().removeClass('ok no');
    lcy.userPanningEnabled(true);
    lcy.autoungrabify(false);
    const target = lcy.nodes('.real').filter(n => {
        const box = n.boundingBox();
        return position.x >= box.x1 && position.x <= box.x2 && position.y >= box.y1 && position.y <= box.y2;
    })[0];
    const layout = target && dropped(target.id());
    drag = null;
    if (layout) apply(layout);
}

// --- Editing ---

/** The side's layout as the plan stores it (see engine/logistics.py). */
function currentLayout() {
    return {
        fixed: view.data.fixed,
        nodes: view.data.nodes.filter(n => PORTS[n.kind]).map(n => ({ id: n.id, kind: n.kind, item: n.item })),
        belts: view.data.belts.map(b => ({ from: b.from, to: b.to, overflow: !!b.overflow }))
    };
}

/** Why the layout can't be built (null if it can): different items, too many belts on a port, a loop. */
function problem(layout) {
    const nodes = Object.fromEntries(view.data.nodes.map(n => [n.id, n]));
    layout.nodes.forEach(n => { if (!nodes[n.id]) nodes[n.id] = n; });
    const ins = {}, outs = {};
    for (const belt of layout.belts) {
        const source = nodes[belt.from], target = nodes[belt.to];
        if (source.item !== target.item) return `A belt can't join ${source.item} to ${target.item}.`;
        outs[belt.from] = (outs[belt.from] || 0) + 1;
        ins[belt.to] = (ins[belt.to] || 0) + 1;
    }
    for (const node of Object.values(nodes)) {
        const [maxIn, maxOut] = ports(node);
        if (maxIn !== null && (ins[node.id] || 0) > maxIn) {
            if (node.kind === 'exit') return `${nameOf(node)} merges up to ${maxIn} belts, and has them all.`;
            return `${nameOf(node)} takes ${maxIn || 'no'} belt${maxIn === 1 ? '' : 's'} in.`;
        }
        if (maxOut !== null && (outs[node.id] || 0) > maxOut) {
            if (node.kind === 'entry') return `${nameOf(node)} splits into up to ${maxOut} belts, and has them all.`;
            return `${nameOf(node)} has ${maxOut || 'no'} belt${maxOut === 1 ? '' : 's'} out.`;
        }
    }
    // Trees only for now: no belt may lead back to where it started
    const next = {};
    layout.belts.forEach(b => (next[b.from] = next[b.from] || []).push(b.to));
    const visit = {};
    const loops = id => {
        if (visit[id] === 1) return true;
        if (visit[id] === 2) return false;
        visit[id] = 1;
        const found = (next[id] || []).some(loops);
        visit[id] = 2;
        return found;
    };
    if (Object.keys(nodes).some(loops)) return 'That belt would make a loop: only trees for now.';
    return null;
}

function nameOf(node) {
    return node.kind === 'building' ? `${view.node.building} ${node.building.slice(1)}` : label(node).split('\n')[0];
}

function apply(layout) {
    const reason = problem(layout);
    if (reason) {
        toast(reason);
        return;
    }
    view.onChange(layout);
}

function addPart(kind) {
    const layout = currentLayout();
    const item = itemsOf().length > 1 ? $('lv-item').value : itemsOf()[0];
    const ids = new Set(view.data.nodes.map(n => n.id));
    let count = view.data.nodes.length + 1;
    while (ids.has(`${PREFIX[kind]}${count}`)) count++;
    layout.nodes.push({ id: `${PREFIX[kind]}${count}`, kind, item });
    apply(layout);
}

function deleteSelected() {
    const selected = lcy.$(':selected')[0];
    if (!selected) return;
    const layout = currentLayout();
    if (selected.isEdge()) {
        layout.belts = layout.belts.filter(b => !(b.from === selected.source().id() && b.to === selected.target().id()));
    } else if (PORTS[selected.data('raw').kind]) {
        const id = selected.id();
        layout.nodes = layout.nodes.filter(n => n.id !== id);
        layout.belts = layout.belts.filter(b => b.from !== id && b.to !== id);
    } else {
        toast("Buildings, entries and exits come from the plan: they can't be deleted.");
        return;
    }
    apply(layout);
}

function toggleOverflow() {
    const selected = lcy.$('edge:selected')[0];
    if (!selected) return;
    const layout = currentLayout();
    const belt = layout.belts.find(b => b.from === selected.source().id() && b.to === selected.target().id());
    belt.overflow = !belt.overflow;
    apply(layout);
}

function updateButtons() {
    if (!lcy) return;
    const selected = lcy.$(':selected')[0];
    $('lv-delete').disabled = !selected;
    $('lv-overflow').disabled = !(selected && selected.isEdge() && selected.source().data('raw').kind === 'overflow');
}

document.querySelectorAll('.lv-add').forEach(button => button.addEventListener('click', () => addPart(button.dataset.kind)));
$('lv-delete').addEventListener('click', deleteSelected);
$('lv-overflow').addEventListener('click', toggleOverflow);
$('lv-reset').addEventListener('click', () => view && view.onChange(null));
$('lv-back').addEventListener('click', closeView);
document.addEventListener('keydown', e => {
    if (!view || e.target.closest('input, textarea, select')) return;
    if (e.key === 'Escape') closeView();
    else if (e.key === 'Delete' || e.key === 'Backspace') deleteSelected();
});
