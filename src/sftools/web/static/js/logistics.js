// Logistics mode (ticket 033): the zoomed-in view of one logistics node, the input or output side of a
// production node. Its buildings, entries/exits, splitters, mergers and buffers are nodes here, and its
// belts edges. Drag from one node to another to lay a belt. Every change is checked here first, then
// sent as the side's layout; the server simulates the flows (engine/logistics.py).
import { state } from './state.js';
import { textColorOn } from './graph.js';
import { showToast as toast } from './panel.js';

const $ = id => document.getElementById(id);

const PREFIX = { splitter: 's', merger: 'm', overflow: 'o', buffer: 'u' };
const PORTS = { splitter: [1, 3], overflow: [1, 3], merger: [3, 1], buffer: [null, 0] };  // [in, out]; null: any
const PART_LABELS = { splitter: 'Splitter', merger: 'Merger', overflow: 'Smart Splitter', buffer: 'Buffer' };
const EPSILON = 1e-4;

let lcy = null;
let view = null;  // { node, side, data, onChange, describe }
let dragging = null;  // the node a belt is being dragged from

function createGraph() {
    lcy = cytoscape({
        container: $('lcy'),
        autoungrabify: true,  // dragging lays belts; the layout places the nodes
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
            { selector: '.buffer', style: { 'shape': 'barrel', 'width': 70 } },
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
            { selector: '.ghost', style: { 'width': 1, 'height': 1, 'opacity': 0, 'label': '' } },
            { selector: 'edge.ghost', style: { 'opacity': 0.7, 'line-style': 'dotted', 'label': '' } },
            { selector: ':selected', style: { 'border-color': '#f43f5e', 'border-width': 4, 'line-color': '#f43f5e', 'target-arrow-color': '#f43f5e' } }
        ],
        minZoom: 0.1,
        maxZoom: 4
    });

    // Lay a belt: press on a node, drag, release on another one
    lcy.on('tapstart', 'node', evt => {
        dragging = evt.target;
        lcy.add([
            { group: 'nodes', data: { id: '__ghost' }, position: { ...evt.position }, classes: 'ghost' },
            { group: 'edges', data: { id: '__ghost_edge', source: dragging.id(), target: '__ghost' }, classes: 'ghost' }
        ]);
    });
    lcy.on('tapdrag', evt => {
        if (dragging) lcy.getElementById('__ghost').position({ ...evt.position });
    });
    lcy.on('tapend', evt => {
        if (!dragging) return;
        const source = dragging;
        dragging = null;
        lcy.remove('.ghost');
        const target = lcy.nodes().filter(n => {
            const box = n.boundingBox();
            return evt.position.x >= box.x1 && evt.position.x <= box.x2 && evt.position.y >= box.y1 && evt.position.y <= box.y2;
        })[0];
        if (target && target.id() !== source.id()) addBelt(source.id(), target.id());
    });
    lcy.on('select unselect', updateButtons);
}

/** Opens the zoomed-in view. `describe(id)` names a production node; `onChange(layout|null)` applies an edit. */
export function openView(node, side, onChange, describe) {
    view = { node, side, data: node.logistics[side], onChange, describe };
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

    const selected = lcy.$(':selected').map(e => e.id());
    const elements = data.nodes.map(node => {
        const color = state.colors[node.item] || '#334155';
        const short = node.delivered !== undefined && node.delivered < node.rate - EPSILON;
        return {
            group: 'nodes',
            data: { id: node.id, label: label(node), raw: node, color, textColor: textColorOn(color) },
            classes: [node.kind, PART_LABELS[node.kind] && node.kind !== 'buffer' && 'part', short && 'short'].filter(Boolean)
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
    selected.forEach(id => lcy.getElementById(id).select());
    const layout = lcy.layout({ name: 'dagre', rankDir: 'LR', nodeSep: 30, rankSep: 90 });
    if (fit) layout.one('layoutstop', () => lcy.fit(undefined, 30));
    layout.run();
    updateButtons();
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
        if (maxIn !== null && (ins[node.id] || 0) > maxIn) return `${nameOf(node)} takes ${maxIn || 'no'} belt${maxIn === 1 ? '' : 's'} in.`;
        if (maxOut !== null && (outs[node.id] || 0) > maxOut) return `${nameOf(node)} has ${maxOut || 'no'} belt${maxOut === 1 ? '' : 's'} out.`;
    }
    // Trees only for now: no belt may lead back to where it started
    const next = {};
    layout.belts.forEach(b => (next[b.from] = next[b.from] || []).push(b.to));
    const state_ = {};
    const loops = id => {
        if (state_[id] === 1) return true;
        if (state_[id] === 2) return false;
        state_[id] = 1;
        const found = (next[id] || []).some(loops);
        state_[id] = 2;
        return found;
    };
    if (Object.keys(nodes).some(loops)) return 'That belt would make a loop: only trees for now.';
    return null;
}

function ports(node) {
    if (node.kind === 'building') return view.side === 'out' ? [0, 1] : [1, 0];
    if (node.kind === 'exit') return [node.lines, 0];
    if (node.kind === 'entry') return [0, node.lines];
    return PORTS[node.kind];
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

function addBelt(from, to) {
    const layout = currentLayout();
    if (layout.belts.some(b => b.from === from && b.to === to)) return;
    const source = view.data.nodes.find(n => n.id === from);
    // A smart splitter's first output is its main one; later ones take the overflow
    const overflow = source.kind === 'overflow' && layout.belts.some(b => b.from === from);
    layout.belts.push({ from, to, overflow });
    apply(layout);
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
