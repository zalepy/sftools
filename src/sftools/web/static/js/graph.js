// Cytoscape graph: rendering, zoom controls, node selection and drag-to-merge.
// cytoscape and cytoscapeDagre are globals from the CDN scripts in index.html.
import { state, MODE } from './state.js';

const DEFAULT_NODE_COLOR = '#334155';
const LIGHT_TEXT = '#f8fafc';
const DARK_TEXT = '#0f172a';
const MERGE_DISTANCE = 60;
const EPSILON = 0.0001;

try {
    if (typeof cytoscapeDagre !== 'undefined') {
        cytoscape.use(cytoscapeDagre);
    }
} catch (e) {
    console.warn("Could not register cytoscape-dagre", e);
}

const cy = cytoscape({
    container: document.getElementById('cy'),
    style: [
        {
            selector: 'node',
            style: {
                'background-color': 'data(backgroundColor)',
                'border-width': 2,
                'border-color': '#f59e0b',
                'label': 'data(label)',
                'color': 'data(textColor)',
                'text-valign': 'center',
                'text-halign': 'center',
                'text-wrap': 'wrap',
                'width': 150,
                'height': 80,
                'shape': 'round-rectangle',
                'font-size': '12px'
            }
        },
        {
            // Status dot, only on nodes that have one
            selector: 'node[backgroundImage]',
            style: {
                'background-image': 'data(backgroundImage)',
                'background-clip': 'node',
                'background-position-x': '0px',
                'background-position-y': '0px'
            }
        },
        {
            selector: 'edge',
            style: {
                'width': 2,
                'line-color': '#475569',
                'target-arrow-color': '#475569',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier',
                'label': 'data(label)',
                'color': '#94a3b8',
                'font-size': '10px',
                'text-background-opacity': 1,
                'text-background-color': '#0f172a',
                'text-background-padding': '2px'
            }
        },
        {
            selector: '.clocked',
            style: {
                'border-color': '#22d3ee',
                'border-style': 'dashed'
            }
        },
        {
            // Demanded by the user (a demand row), alone or in a merge group
            selector: '.external',
            style: {
                'border-width': 3,
                'border-color': '#a855f7'
            }
        },
        {
            // Supplied from outside the plan
            selector: '.supplied',
            style: {
                'border-width': 3,
                'border-color': '#38bdf8'
            }
        },
        {
            // Where by-products go (ticket 024)
            selector: '.sink',
            style: {
                'shape': 'ellipse',
                'width': 120,
                'height': 120,
                'border-width': 3,
                'border-color': '#94a3b8'
            }
        },
        {
            // Fluids can't be sunk: the Sink only holds them as a placeholder
            selector: '.sink.invalid',
            style: {
                'border-width': 8,
                'border-color': '#ef4444'
            }
        },
        {
            selector: 'edge.byproduct',
            style: {
                'line-style': 'dotted',
                'line-color': '#64748b',
                'target-arrow-color': '#64748b'
            }
        },
        {
            // A by-product used as supply (ticket 031)
            selector: 'edge.byproduct.used',
            style: {
                'line-style': 'dashed',
                'line-color': '#38bdf8',
                'target-arrow-color': '#38bdf8',
                'color': '#7dd3fc'
            }
        },
        {
            // Using it would close a loop, so it goes to the Sink
            selector: 'edge.byproduct.loop',
            style: {
                'line-color': '#f59e0b',
                'target-arrow-color': '#f59e0b',
                'color': '#fcd34d'
            }
        },
        {
            selector: 'edge.byproduct.invalid',
            style: {
                'line-color': '#ef4444',
                'target-arrow-color': '#ef4444',
                'color': '#fca5a5'
            }
        },
        {
            // All its buildings are built (ticket 037): faded, so what's left to build stands out
            selector: '.done',
            style: { 'opacity': 0.45 }
        },
        {
            // Logistics mode: a node's input (left) and output (right) logistics, with its number of
            // splitters and mergers (ticket 033)
            selector: '.lnode',
            style: {
                'shape': 'rectangle',
                'width': 22,
                'height': 50,
                'background-color': '#1e293b',
                'border-width': 2,
                'border-color': '#94a3b8',
                'color': '#e2e8f0',
                'font-size': '11px'
            }
        },
        {
            // An edge that needs more than one belt (or pipe) of the highest tier unlocked
            selector: 'edge.multi',
            style: { 'line-color': '#f59e0b', 'target-arrow-color': '#f59e0b', 'width': 4 }
        },
        {
            selector: '.lnode.edited',
            style: { 'border-style': 'dashed', 'border-color': '#38bdf8' }
        },
        {
            selector: '.lnode.warn',
            style: { 'border-width': 3, 'border-color': '#ef4444' }
        },
        {
            // Last, so it shows on overridden nodes too; the node keeps its item color
            selector: ':selected',
            style: {
                'border-width': 4,
                'border-color': '#f43f5e'
            }
        }
    ],
    layout: {
        name: 'dagre',
        rankDir: 'LR',
        nodeSep: 60,
        rankSep: 120
    },
    minZoom: 0.05,
    maxZoom: 10
});

// --- Zoom controls ---

const zoomSlider = document.getElementById('zoom-slider');
const zoomPercent = document.getElementById('zoom-percent');

function updateZoomSlider() {
    const z = cy.zoom();
    zoomSlider.value = z;
    zoomPercent.innerText = Math.round(z * 100) + '%';
}

zoomSlider.addEventListener('input', (e) => {
    const z = parseFloat(e.target.value);
    cy.zoom({
        level: z,
        renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 }
    });
    zoomPercent.innerText = Math.round(z * 100) + '%';
});

cy.on('zoom', updateZoomSlider);

// Cytoscape's own wheel zoom jumps (51% -> 135% for one mouse tick). Handle the wheel here instead,
// before Cytoscape sees it: about 15% per mouse tick, toward the cursor; trackpads send smaller deltas.
const WHEEL_ZOOM_RATE = 0.0015;  // per pixel of scroll
const LINE_HEIGHT = 33;          // pixels per line, for wheels that report lines

// Cytoscape listens on its container, so catch the event on the way down, at the parent.
cy.container().parentElement.addEventListener('wheel', e => {
    if (!cy.container().contains(e.target)) return;
    e.preventDefault();
    e.stopPropagation();
    const pixels = e.deltaMode === WheelEvent.DOM_DELTA_LINE ? e.deltaY * LINE_HEIGHT : e.deltaY;
    const box = cy.container().getBoundingClientRect();
    cy.zoom({
        level: cy.zoom() * Math.pow(1 + WHEEL_ZOOM_RATE, -pixels),
        renderedPosition: { x: e.clientX - box.left, y: e.clientY - box.top }
    });
}, { capture: true, passive: false });

/** Call after the graph's container changes size (Cytoscape only notices window resizes). */
export function resizeGraph() {
    cy.resize();
}

export function fitView() {
    cy.fit();
    updateZoomSlider();
}

// --- Rendering ---

function colorFor(item) {
    return state.colors[item] || DEFAULT_NODE_COLOR;
}

// WCAG relative luminance of a #rrggbb color
function luminance(hex) {
    const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
    const [r, g, b] = channels.map(c => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Light or dark text, whichever contrasts more with the background. */
export function textColorOn(background) {
    if (!/^#[0-9a-f]{6}$/i.test(background)) return LIGHT_TEXT;
    const bg = luminance(background);
    const contrast = text => (Math.max(bg, text) + 0.05) / (Math.min(bg, text) + 0.05);
    return contrast(luminance(DARK_TEXT)) > contrast(luminance(LIGHT_TEXT)) ? DARK_TEXT : LIGHT_TEXT;
}

/** Whether the user demands this node (or a node merged into it) directly. */
export function isExternalDemand(node) {
    return ((node.parent_demands || {})['External Demand'] || 0) > 0;
}

/**
 * Buildings needed and built (ticket 037), or null for nodes without buildings to build (inbound
 * production, supplied from outside). Built counts are kept per recipe: after a recipe switch they no
 * longer count, and `stale` holds the old mark.
 */
export function builtStatus(node) {
    if (!node || node.inbound || node.is_supplied) return null;
    const needed = node.clocks && node.clocks.length ? node.buildings : Math.ceil(parseFloat(node.building_scale) - EPSILON);
    if (!(needed > 0)) return null;
    const mark = state.built[node.id];
    const current = mark && mark.recipe === node.recipe_name;
    const built = current ? mark.count : 0;
    return { needed, built, done: built >= needed, stale: mark && !current ? mark : null };
}

// Small dot in the top-right corner: blue = a whole building or more spare, green = surplus, red = shortage
function statusColor(node) {
    const surplus = parseFloat(node.building_scale) - parseFloat(node.ideal_building_scale);
    if (surplus > 1 - EPSILON) return '#3b82f6';
    if (surplus > EPSILON) return '#22c55e';
    if (surplus < -EPSILON) return '#ef4444';
    return null;
}

// Top-left: a check when all buildings are built, "6/8" when some are (and "10/8" past done)
function builtBadge(node) {
    const status = builtStatus(node);
    if (!status || status.built === 0) return '';
    const check = status.done
        ? '<circle cx="12" cy="12" r="8" fill="#16a34a" /><path d="M8 12 l3 3 l5 -6" stroke="#fff" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round" />'
        : '';
    if (status.built === status.needed) return check;
    const text = `${status.built}/${status.needed}`;
    const x = status.done ? 24 : 4;
    const width = 7 * text.length + 8;
    return `${check}<rect x="${x}" y="4" width="${width}" height="16" rx="4" fill="#0f172a" fill-opacity="0.85" />` +
        `<text x="${x + width / 2}" y="16" font-family="sans-serif" font-size="12" text-anchor="middle" fill="#e2e8f0">${text}</text>`;
}

/** The node's badges as an image (the status dot and the built mark), or null when it has none. */
function badgeImage(node) {
    const color = statusColor(node);
    const parts = (color ? `<circle cx="140" cy="10" r="6" fill="${color}" />` : '') + builtBadge(node);
    if (!parts) return null;
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="150" height="80">${parts}</svg>`;
    return `data:image/svg+xml;base64,${btoa(svg)}`;
}

function isDone(node) {
    const status = builtStatus(node);
    return Boolean(status && status.done);
}

/** "10×", or "8 × 100% + 1 × 200%" when any building runs at another clock. */
export function clocksText(node, separator = ' × ') {
    const groups = (node.clocks || []).filter(g => g.count > 0);
    if (groups.length === 0 || groups.every(g => g.clock === 1)) return '';
    return groups.map(g => `${g.count}${separator}${+(g.clock * 100).toFixed(2)}%`).join(' + ');
}

/** Number of buildings: whole with clocks, otherwise the fractional scale. */
export function buildingsText(node) {
    return node.clocks && node.clocks.length ? `${node.buildings}` : parseFloat(node.building_scale).toFixed(2);
}

export function renderGraph(nodesData) {
    if (!Array.isArray(nodesData)) {
        console.warn("renderGraph called with invalid nodesData", nodesData);
        return;
    }
    const nodeMap = Object.fromEntries(nodesData.map(node => [node.id, node]));
    const elements = [];

    nodesData.forEach(node => {
        const badges = badgeImage(node);
        const part = node.split ? ` [${node.split.part}/${node.split.count}]` : '';
        const alternate = node.is_alternate ? ' (A)' : '';
        // A fourth line only when some building runs at another clock than 100%
        const clocks = clocksText(node, '×');
        const shards = node.power_shards ? ` · ${node.power_shards} shards` : '';
        const clockLine = clocks || shards ? `\n${clocks}${shards}` : '';
        const made = node.inbound ? 'inbound'
            : node.sink ? `${node.buildings}× ${node.building}`
            : node.is_supplied ? 'supplied from outside' : `${buildingsText(node)}× ${node.building}`;
        const of = node.inbound ? ` of ${parseFloat(node.inbound.rate).toFixed(2)}` : '';
        const fluids = node.sink && node.sink.fluids.length ? '\nfluids can\'t be sunk!' : '';
        const label = `${node.output_item}${alternate}${part}\n${parseFloat(node.throughput).toFixed(2)}${of}/m\n(${made})${clockLine}${fluids}`;
        const color = colorFor(node.output_item);
        const classes = [
            state.clocks[node.id] && 'clocked',
            isExternalDemand(node) && 'external',
            node.is_supplied && 'supplied',
            node.sink && 'sink',
            fluids && 'invalid',
            isDone(node) && 'done'
        ].filter(Boolean);
        elements.push({
            group: 'nodes',
            data: {
                id: node.id,
                label,
                raw: node,
                backgroundColor: color,
                textColor: textColorOn(color),
                ...(badges && { backgroundImage: badges })
            },
            classes
        });
    });

    // Edges point from supplier to consumer, labelled with what this supplier provides to it. A merged
    // consumer can have several suppliers of an item, each covering one branch's share (parent_demands).
    nodesData.forEach(node => {
        (node.parents || []).forEach(parentId => {
            if (!nodeMap[parentId]) return;
            const rate = (node.parent_demands || {})[parentId] || 0;
            const belts = beltText((node.edge_belts || {})[parentId]);
            elements.push({
                group: 'edges',
                data: {
                    source: node.id,
                    target: parentId,
                    label: rate > 0 ? `${rate.toFixed(2)}/m${belts}` : ''
                },
                classes: (node.edge_belts || {})[parentId]?.count > 1 ? ['multi'] : []
            });
        });
    });

    // By-products: from each maker to the nodes it supplies, and what's left to the Sink (fluids in red)
    nodesData.forEach(node => {
        (node.byproducts || []).forEach(byproduct => {
            const solved = byproduct.solving ? ' (loop, solved)' : '';
            Object.entries(byproduct.used).forEach(([consumer, rate]) => {
                if (!nodeMap[consumer]) return;
                elements.push({
                    group: 'edges',
                    data: { source: node.id, target: consumer, maker: node.id,
                        label: `${rate.toFixed(2)}/m ${byproduct.item}${solved}${beltText((byproduct.edge_belts || {})[consumer])}` },
                    classes: ['byproduct', 'used', byproduct.solving && 'loop'].filter(Boolean)
                });
            });
        });
    });
    nodesData.filter(node => node.sink).forEach(sink => {
        sink.sink.inputs.forEach(input => {
            if (!nodeMap[input.from]) return;
            const loop = input.loop ? ' (loop)' : '';
            const maker = (nodeMap[input.from].byproducts || []).find(b => b.item === input.item);
            const belts = beltText(((maker || {}).edge_belts || {}).sink);
            elements.push({
                group: 'edges',
                data: { source: input.from, target: sink.id, label: `${input.rate.toFixed(2)}/m ${input.item}${loop}${belts}`, maker: input.from },
                classes: ['byproduct', input.fluid && 'invalid', input.loop && 'loop'].filter(Boolean)
            });
        });
    });

    cy.elements().remove();
    cy.add(elements);

    // Logistics nodes stand beside their production node: wider spacing, then attached after the layout
    const logistics = MODE === 'logistics';
    const layout = cy.layout({ name: 'dagre', rankDir: 'LR', nodeSep: 50, rankSep: logistics ? 160 : 100 });
    layout.one('layoutstop', () => {
        if (logistics) attachLogistics(nodesData);
        fitView();
    });
    layout.run();
}

/** " · Mk.3", " · 2× Mk.6" or " · pipe Mk.1" for an edge's belts (logistics mode; see belts_needed). */
function beltText(belts) {
    if (!belts) return '';
    const count = belts.count > 1 ? `${belts.count}× ` : '';
    return ` · ${count}${belts.kind === 'pipe' ? 'pipe ' : ''}Mk.${belts.tier}`;
}

const LOGISTICS_GAP = 14;  // between a production node and its logistics nodes

function attachLogistics(nodesData) {
    const added = [];
    nodesData.forEach(node => {
        ['in', 'out'].forEach(side => {
            const data = (node.logistics || {})[side];
            if (!data) return;
            added.push({
                group: 'nodes',
                data: { id: `${node.id}|${side}`, label: String(data.complexity), owner: node.id, side, raw: data, logistics: true },
                classes: ['lnode', data.warnings.length && 'warn', data.edited && 'edited'].filter(Boolean),
                grabbable: false
            });
        });
    });
    cy.add(added);
    positionLogistics(cy.nodes().not('.lnode'));
    // Belts run from a node's output logistics to the consumer's input logistics
    cy.edges().forEach(edge => {
        const source = cy.getElementById(`${edge.source().id()}|out`);
        const target = cy.getElementById(`${edge.target().id()}|in`);
        const move = {};
        if (source.length) move.source = source.id();
        if (target.length) move.target = target.id();
        if (Object.keys(move).length) edge.move(move);
    });
}

function positionLogistics(nodes) {
    nodes.forEach(node => {
        const { x, y } = node.position();
        const offset = node.width() / 2 + LOGISTICS_GAP;
        cy.getElementById(`${node.id()}|in`).position({ x: x - offset, y });
        cy.getElementById(`${node.id()}|out`).position({ x: x + offset, y });
    });
}

// Logistics nodes follow their production node when it's dragged
cy.on('position', 'node[!logistics]', evt => {
    if (MODE === 'logistics') positionLogistics(evt.target);
});

export function refreshNodeColors() {
    cy.nodes().not('.lnode').forEach(node => {
        const color = colorFor(node.data('raw').output_item);
        node.data({ backgroundColor: color, textColor: textColorOn(color) });
    });
}

/** Redraws the built marks after state.built changed; nothing else needs the server. */
export function refreshBuilt() {
    cy.nodes().not('.lnode').forEach(node => {
        const raw = node.data('raw');
        const badges = badgeImage(raw);
        if (badges) node.data('backgroundImage', badges); else node.removeData('backgroundImage');
        node.toggleClass('done', isDone(raw));
    });
}

export function hasNodes() {
    return cy.nodes().length > 0;
}

/** Node data as returned by the server, or null. */
export function getNodeData(nodeId) {
    const node = cy.getElementById(nodeId);
    return node && node.length > 0 ? node.data('raw') : null;
}

// --- Interaction ---

export function onNodeSelected(callback) {
    cy.on('tap', 'node[!logistics]', evt => callback(evt.target.data('raw')));
}

/** Calls callback(production node id, 'in' | 'out') when a logistics node is clicked. */
export function onLogisticsSelected(callback) {
    cy.on('tap', 'node.lnode', evt => callback(evt.target.data('owner'), evt.target.data('side')));
}

/** A logistics side of a production node, as the server returned it, or null. */
export function getLogistics(nodeId, side) {
    const node = cy.getElementById(`${nodeId}|${side}`);
    return node && node.length > 0 ? node.data('raw') : null;
}

export function selectLogistics(nodeId, side) {
    const node = cy.getElementById(`${nodeId}|${side}`);
    if (node && node.length > 0) node.emit('tap');
}

/** Calls callback(maker node id) when a by-product edge is clicked. */
export function onByproductSelected(callback) {
    cy.on('tap', 'edge.byproduct', evt => callback(evt.target.data('maker')));
}

/** Re-runs the selection callback for a node, e.g. after the graph was re-rendered. */
export function reselectNode(nodeId) {
    const node = cy.getElementById(nodeId);
    if (node && node.length > 0) {
        node.emit('tap');
    }
}

/** Calls callback(sourceId, targetId) when a node is dropped onto another node with the same output item. */
export function onMergeDrop(callback) {
    cy.on('dragfree', 'node', evt => {
        const dragNode = evt.target;
        const dragPos = dragNode.position();
        const dragData = dragNode.data('raw');

        const overlapping = cy.nodes().not('.lnode').filter(n => {
            if (n.id() === dragNode.id()) return false;
            const pos = n.position();
            return Math.hypot(pos.x - dragPos.x, pos.y - dragPos.y) < MERGE_DISTANCE;
        });
        if (overlapping.length === 0) return;

        const targetNode = overlapping[0];
        if (dragData.output_item !== targetNode.data('raw').output_item) return;
        // Inbound production and the Sink aren't nodes of the plan
        if ([dragData, targetNode.data('raw')].some(data => data.inbound || data.sink)) return;

        // Let Cytoscape finish the drag before the graph is re-rendered
        setTimeout(() => callback(dragNode.id(), targetNode.id()), 50);
    });
}
