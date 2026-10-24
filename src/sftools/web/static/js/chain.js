// The chain tab (ticket 040): how the plan tabs feed each other. Each tab is a box with its demand
// targets as supplies (right) and its inbound production as needs (left); the user links a supply to a
// need of the same item, which also records that the connection is routed in the game. Nothing here
// changes a plan: rates are derived from the plans, and highlights show where they don't add up.
import { state } from './state.js';
import { smoothWheelZoom } from './graph.js';
import { textColorOn } from './node-info.js';
import { chainEnds } from './supply-info.js';
import { showToast as toast } from './panel/messages.js';
import { getBook, saveBook } from './tabs.js';

const $ = id => document.getElementById(id);

const EPSILON = 1e-4;
const ROW = 60;         // between nodes in a box
const INSIDE = 100;     // from a box's middle to its needs (left) and supplies (right)
const COLUMN = 480;     // between columns of boxes
const GAP = 70;         // between boxes in a column

let ccy = null;
let shown = null;  // { onOpenTab(id) } while the chain tab is shown
let drag = null;   // the supply a link is being drawn from

const rate = value => `${value.toFixed(2)}/m`;

function chain() {
    return getBook().chain;
}

// --- What the plans say ---

/** The supplies (demand targets) and needs (inbound production) of every tab, with their rates. */
function endpoints() {
    const nodes = new Map();
    getBook().tabs.forEach(tab => {
        const plan = tab.plan || {};
        const add = (kind, item, value) => {
            const amount = parseFloat(value);
            if (!item || !(amount > 0)) return;
            const id = nodeId(kind, tab.id, item);
            const node = nodes.get(id) || { id, kind, tab: tab.id, item, rate: 0 };
            node.rate += amount;
            nodes.set(id, node);
        };
        const { supplies, needs } = chainEnds(plan, state.power);
        supplies.forEach(entry => add('supply', entry.item, entry.rate));
        needs.forEach(entry => add('need', entry.item, entry.rate));
    });
    return nodes;
}

function nodeId(kind, tab, item) {
    return `${kind === 'supply' ? 's' : 'n'}|${tab}|${item}`;
}

function linkId(link) {
    return `l|${link.from.tab}|${link.to.tab}|${link.from.item}`;
}

const supplyOf = link => nodeId('supply', link.from.tab, link.from.item);
const needOf = link => nodeId('need', link.to.tab, link.to.item);

/**
 * The links both of whose ends are in the plans. The others stay hidden (a plan may get its demand target
 * or inbound production back) until a new link shares an end with them (see dropHidden).
 */
function liveLinks(nodes = endpoints()) {
    return chain().links.filter(link => nodes.has(supplyOf(link)) && nodes.has(needOf(link)));
}

/** Drops the hidden links that share an end with `added`: they'd come back as a conflict with it. */
function dropHidden(added) {
    const live = new Set(liveLinks().map(linkId));
    chain().links = chain().links.filter(l =>
        live.has(linkId(l)) || (supplyOf(l) !== supplyOf(added) && needOf(l) !== needOf(added)));
}

/**
 * The links whose ends are in the plans, with their rates, and what each node gets or gives. One supply
 * to several needs: each link carries what its need asks for; several supplies to one need: what its
 * supply makes; one to one: the smaller of the two.
 */
function flows(nodes) {
    const links = liveLinks(nodes);
    const count = {};
    links.forEach(link => [supplyOf(link), needOf(link)].forEach(id => { count[id] = (count[id] || 0) + 1; }));
    const flowing = {};
    const result = links.map(link => {
        const supply = nodes.get(supplyOf(link)), need = nodes.get(needOf(link));
        const fanOut = count[supply.id] > 1, fanIn = count[need.id] > 1;
        const value = fanOut && fanIn ? null : fanOut ? need.rate : fanIn ? supply.rate : Math.min(supply.rate, need.rate);
        [supply.id, need.id].forEach(id => { flowing[id] = (flowing[id] || 0) + (value || 0); });
        return { link, rate: value };
    });
    return { links: result, flowing, count };
}

/** short: gives more than it makes, or gets less than it needs; surplus: the other way; ok: matches. */
function status(node, flowing, count) {
    if (!count[node.id]) return null;
    const flow = flowing[node.id] || 0;
    if (Math.abs(flow - node.rate) <= EPSILON) return { kind: 'ok', text: '' };
    const shortfall = node.kind === 'supply' ? flow > node.rate : flow < node.rate;
    const difference = rate(Math.abs(flow - node.rate));
    if (node.kind === 'supply') return shortfall ? { kind: 'short', text: `${difference} short` } : { kind: 'surplus', text: `${difference} spare` };
    return shortfall ? { kind: 'short', text: `${difference} short` } : { kind: 'surplus', text: `${difference} more` };
}

// --- Drawing ---

function createGraph() {
    ccy = cytoscape({
        container: $('ccy'),
        boxSelectionEnabled: false,
        style: [
            {
                selector: 'node',
                style: {
                    'label': 'data(label)', 'text-wrap': 'wrap', 'text-valign': 'center', 'text-halign': 'center',
                    'font-size': '11px', 'width': 160, 'height': 44, 'shape': 'round-rectangle',
                    'border-width': 2, 'border-color': '#64748b'
                }
            },
            { selector: 'node[color]', style: { 'background-color': 'data(color)', 'color': 'data(textColor)' } },
            {
                selector: '.box',
                style: {
                    'shape': 'round-rectangle', 'background-color': '#1e293b', 'background-opacity': 1, 'border-color': '#94a3b8',
                    'color': '#e2e8f0', 'font-size': '14px', 'font-weight': 'bold', 'text-valign': 'top', 'text-margin-y': -6,
                    'padding': '18px'
                }
            },
            { selector: '.box.empty', style: { 'width': 200, 'height': 40, 'text-valign': 'center', 'text-margin-y': 0, 'font-weight': 'normal', 'color': '#94a3b8' } },
            { selector: '.need', style: { 'shape': 'tag' } },
            { selector: '.ok', style: { 'border-color': '#22c55e', 'border-width': 3 } },
            { selector: '.surplus', style: { 'border-color': '#3b82f6', 'border-width': 4 } },
            { selector: '.short', style: { 'border-color': '#ef4444', 'border-width': 4 } },
            {
                selector: 'edge',
                style: {
                    'width': 3, 'line-color': '#64748b', 'target-arrow-color': '#64748b', 'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier', 'label': 'data(label)', 'font-size': '11px', 'color': '#cbd5e1',
                    'text-background-opacity': 1, 'text-background-color': '#0f172a', 'text-background-padding': '2px'
                }
            },
            { selector: ':selected', style: { 'line-color': '#f43f5e', 'target-arrow-color': '#f43f5e', 'border-color': '#f43f5e', 'border-width': 4 } },
            // While a link is drawn: where it can go, and where it can't
            { selector: '.can', style: { 'border-color': '#22c55e', 'border-width': 5 } },
            { selector: '.cannot', style: { 'opacity': 0.35 } },
            { selector: '.ghost', style: { 'width': 1, 'height': 1, 'opacity': 0, 'label': '' } },
            { selector: 'edge.ghost', style: { 'opacity': 0.7, 'line-style': 'dotted', 'label': '' } }
        ],
        minZoom: 0.1,
        maxZoom: 3
    });

    ccy.on('tapstart', 'node.supply', evt => startDrag(evt.target));
    ccy.on('tapdrag', evt => {
        if (drag) ccy.getElementById('__ghost').position({ ...evt.position });
    });
    ccy.on('tapend', evt => {
        if (drag) endDrag(evt.position);
    });
    ccy.on('select unselect', updateButtons);
    ccy.on('dragfree', 'node.box', () => {
        rememberPositions();
        saveBook();
    });
    ccy.on('dbltap', 'node.box', evt => shown && shown.onOpenTab(evt.target.data('tab')));
    smoothWheelZoom(ccy);
}

/** Where each box goes: where the user put it, else in columns by what feeds what. */
function placement(boxes) {
    const saved = chain().positions;
    const feeds = {};
    chain().links.forEach(link => (feeds[link.to.tab] = feeds[link.to.tab] || new Set()).add(link.from.tab));
    const rank = {};
    const rankOf = (tab, seen = new Set()) => {
        if (rank[tab] !== undefined) return rank[tab];
        if (seen.has(tab)) return 0;
        seen.add(tab);
        const from = [...(feeds[tab] || [])].filter(other => other !== tab && boxes.some(b => b.tab === other));
        return (rank[tab] = from.length ? 1 + Math.max(...from.map(other => rankOf(other, seen))) : 0);
    };
    const heights = {};
    const centers = {};
    const bottom = {};
    boxes.forEach(box => {
        const column = rankOf(box.tab);
        const height = Math.max(1, box.rows) * ROW;
        const top = bottom[column] === undefined ? 0 : bottom[column] + GAP;
        centers[box.tab] = saved[box.tab] ? { ...saved[box.tab] } : { x: column * COLUMN, y: top + height / 2 };
        heights[box.tab] = height;
        bottom[column] = top + height;
    });
    return centers;
}

function render(fit) {
    const nodes = endpoints();
    const { links, flowing, count } = flows(nodes);
    const book = getBook();
    const boxes = book.tabs.map(tab => {
        const mine = [...nodes.values()].filter(n => n.tab === tab.id);
        const needs = mine.filter(n => n.kind === 'need'), supplies = mine.filter(n => n.kind === 'supply');
        return { tab: tab.id, name: tab.name, needs, supplies, rows: Math.max(needs.length, supplies.length) };
    });
    const centers = placement(boxes);
    const selected = ccy.$(':selected').map(e => e.id());

    const elements = [];
    boxes.forEach(box => {
        const center = centers[box.tab];
        elements.push({
            group: 'nodes', data: { id: `box|${box.tab}`, tab: box.tab, label: box.rows ? box.name : `${box.name}: no demands or inbound` },
            position: { ...center }, classes: box.rows ? 'box' : 'box empty'
        });
        // A box with one kind only has it in the middle, so the box's middle stays where it's kept
        const place = (list, side) => list.forEach((node, i) => {
            const x = box.needs.length && box.supplies.length ? center.x + side * INSIDE : center.x;
            const state_ = status(node, flowing, count);
            const color = state.colors[node.item] || '#334155';
            elements.push({
                group: 'nodes',
                data: {
                    id: node.id, parent: `box|${box.tab}`, raw: node, color, textColor: textColorOn(color),
                    label: `${node.item}\n${rate(node.rate)}${state_ && state_.text ? `\n${state_.text}` : ''}`
                },
                position: { x, y: center.y + (i - (box.rows - 1) / 2) * ROW },
                grabbable: false,
                classes: [node.kind, state_ && state_.kind].filter(Boolean).join(' ')
            });
        });
        place(box.needs, -1);
        place(box.supplies, 1);
    });
    links.forEach(({ link, rate: value }) => elements.push({
        group: 'edges',
        data: { id: linkId(link), source: supplyOf(link), target: needOf(link), link, label: value === null ? '?' : rate(value) }
    }));

    ccy.elements().remove();
    ccy.add(elements);
    selected.forEach(id => ccy.getElementById(id).select());
    if (fit) ccy.fit(undefined, 40);
    updateButtons();
}

/** Keeps where every box is, in the book. */
function rememberPositions() {
    const positions = {};
    ccy.nodes('.box').forEach(box => {
        const { x, y } = box.position();
        positions[box.data('tab')] = { x: Math.round(x), y: Math.round(y) };
    });
    chain().positions = positions;
}

// --- Linking ---

function startDrag(supply) {
    drag = supply.data('raw');
    ccy.userPanningEnabled(false);
    ccy.autoungrabify(true);
    const anchor = supply.position();
    ccy.add([
        { group: 'nodes', data: { id: '__ghost' }, position: { ...anchor }, classes: 'ghost' },
        { group: 'nodes', data: { id: '__anchor' }, position: { ...anchor }, classes: 'ghost' },
        { group: 'edges', data: { id: '__ghost_edge', source: '__anchor', target: '__ghost' }, classes: 'ghost' }
    ]);
    ccy.nodes('.need, .supply').forEach(node => {
        if (node.id() === supply.id()) return;
        node.addClass(node.hasClass('need') && !problem(link(drag, node.data('raw'))) ? 'can' : 'cannot');
    });
}

function endDrag(position) {
    ccy.remove('.ghost');
    ccy.nodes().removeClass('can cannot');
    ccy.userPanningEnabled(true);
    ccy.autoungrabify(false);
    const target = ccy.nodes('.need').filter(n => {
        const box = n.boundingBox();
        return position.x >= box.x1 && position.x <= box.x2 && position.y >= box.y1 && position.y <= box.y2;
    })[0];
    const from = drag;
    drag = null;
    if (!target) return;
    const added = link(from, target.data('raw'));
    const why = problem(added);
    if (why) {
        toast(why);
        return;
    }
    dropHidden(added);
    chain().links.push(added);
    saveBook();
    render(false);
}

function link(supply, need) {
    return { from: { tab: supply.tab, item: supply.item }, to: { tab: need.tab, item: need.item } };
}

const tabName = id => (getBook().tabs.find(t => t.id === id) || {}).name;

/** Why the link can't be made, or null: another item, the same tab, already there, or many to many. */
function problem(added) {
    if (added.from.item !== added.to.item) return `A link can't join ${added.from.item} to ${added.to.item}.`;
    if (added.from.tab === added.to.tab) return `${tabName(added.from.tab)} can't feed itself.`;
    const links = chain().links;
    if (links.some(l => linkId(l) === linkId(added))) return 'Those are linked already.';
    // The links joined to the new one, through their ends: one supply, or one need, never several of both.
    // Hidden links don't count (see liveLinks).
    const all = [...liveLinks(), added];
    const group = new Set([supplyOf(added), needOf(added)]);
    let grew = true;
    while (grew) {
        grew = false;
        all.forEach(l => {
            const ends = [supplyOf(l), needOf(l)];
            if (ends.some(id => group.has(id)) && !ends.every(id => group.has(id))) {
                ends.forEach(id => group.add(id));
                grew = true;
            }
        });
    }
    const supplies = [...group].filter(id => id.startsWith('s|')).length;
    const needs = group.size - supplies;
    if (supplies > 1 && needs > 1) return `${added.from.item}: one plan can feed several, or several can feed one, not both.`;
    return null;
}

/** Links a supply to a need from outside the chain tab (ticket 045): null when linked, else why not. */
export function addLink(from, to) {
    const added = { from, to };
    if (chain().links.some(l => linkId(l) === linkId(added))) return null;
    const why = problem(added);
    if (why) return why;
    dropHidden(added);
    chain().links.push(added);
    saveBook();
    return null;
}

function deleteSelected() {
    const selected = ccy && ccy.$('edge:selected')[0];
    if (!selected) return;
    chain().links = chain().links.filter(l => linkId(l) !== selected.id());
    saveBook();
    render(false);
}

function updateButtons() {
    $('chain-delete').disabled = !(ccy && ccy.$('edge:selected').length);
}

// --- Showing ---

/** Shows the chain tab over the graph; `onOpenTab(id)` shows a plan tab (double-click on its box). */
export function openChain(onOpenTab) {
    shown = { onOpenTab };
    $('chain-view').hidden = false;
    if (!ccy) createGraph();
    ccy.resize();
    render(true);
}

/** Draws it again after a plan changed. */
export function refreshChain() {
    if (shown) render(false);
}

export function closeChain() {
    shown = null;
    $('chain-view').hidden = true;
}

export function isChainOpen() {
    return shown !== null;
}

$('chain-delete').addEventListener('click', deleteSelected);
$('chain-fit').addEventListener('click', () => ccy && ccy.fit(undefined, 40));
document.addEventListener('keydown', e => {
    if (!shown || e.target.closest('input, textarea, select')) return;
    if (e.key === 'Delete' || e.key === 'Backspace') deleteSelected();
});
