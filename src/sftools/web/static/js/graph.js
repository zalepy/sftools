// Cytoscape graph: rendering, zoom controls, node selection and drag-to-merge.
// cytoscape and cytoscapeDagre are globals from the CDN scripts in index.html.
import { state } from './state.js';

const DEFAULT_NODE_COLOR = '#334155';
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
                'color': '#f8fafc',
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

// Small dot in the top-right corner: blue = a whole building or more spare, green = surplus, red = shortage
function indicatorImage(node) {
    const surplus = parseFloat(node.building_scale) - parseFloat(node.ideal_building_scale);
    let color = null;
    if (surplus > 1 - EPSILON) {
        color = '#3b82f6';
    } else if (surplus > EPSILON) {
        color = '#22c55e';
    } else if (surplus < -EPSILON) {
        color = '#ef4444';
    }
    if (!color) return null;

    const svg = `
        <svg xmlns="http://www.w3.org/2000/svg" width="150" height="80">
            <circle cx="140" cy="10" r="6" fill="${color}" />
        </svg>
    `;
    return `data:image/svg+xml;base64,${btoa(svg)}`;
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
        const indicator = indicatorImage(node);
        const part = node.split ? ` [${node.split.part}/${node.split.count}]` : '';
        const alternate = node.is_alternate ? ' (A)' : '';
        // A fourth line only when some building runs at another clock than 100%
        const clocks = clocksText(node, '×');
        const shards = node.power_shards ? ` · ${node.power_shards} shards` : '';
        const clockLine = clocks || shards ? `\n${clocks}${shards}` : '';
        const label = `${node.output_item}${alternate}${part}\n${parseFloat(node.throughput).toFixed(2)}/m\n(${buildingsText(node)}× ${node.building})${clockLine}`;
        elements.push({
            group: 'nodes',
            data: {
                id: node.id,
                label,
                raw: node,
                backgroundColor: colorFor(node.output_item),
                ...(indicator && { backgroundImage: indicator })
            },
            classes: state.clocks[node.id] ? 'clocked' : ''
        });
    });

    // Edges point from supplier to consumer, labelled with what this supplier provides to it. A merged
    // consumer can have several suppliers of an item, each covering one branch's share (parent_demands).
    nodesData.forEach(node => {
        (node.parents || []).forEach(parentId => {
            if (!nodeMap[parentId]) return;
            const rate = (node.parent_demands || {})[parentId] || 0;
            elements.push({
                group: 'edges',
                data: {
                    source: node.id,
                    target: parentId,
                    label: rate > 0 ? `${rate.toFixed(2)}/m` : ''
                }
            });
        });
    });

    cy.elements().remove();
    cy.add(elements);

    const layout = cy.layout({ name: 'dagre', rankDir: 'LR', nodeSep: 50, rankSep: 100 });
    layout.one('layoutstop', fitView);
    layout.run();
}

export function refreshNodeColors() {
    cy.nodes().forEach(node => {
        node.style('background-color', colorFor(node.data('raw').output_item));
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
    cy.on('tap', 'node', evt => callback(evt.target.data('raw')));
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

        const overlapping = cy.nodes().filter(n => {
            if (n.id() === dragNode.id()) return false;
            const pos = n.position();
            return Math.hypot(pos.x - dragPos.x, pos.y - dragPos.y) < MERGE_DISTANCE;
        });
        if (overlapping.length === 0) return;

        const targetNode = overlapping[0];
        if (dragData.output_item !== targetNode.data('raw').output_item) return;

        // Let Cytoscape finish the drag before the graph is re-rendered
        setTimeout(() => callback(dragNode.id(), targetNode.id()), 50);
    });
}
