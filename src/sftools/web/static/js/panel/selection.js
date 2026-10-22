// The Node tab's other selections: a logistics node, an edge's belts, and a node's by-products.
import { $, EPSILON, updateNodeEmpty, nodeLabel, derivationText } from './common.js';

// --- Selected logistics node (logistics mode) ---

/** Summary of one side's logistics: splitters and mergers, belts, what backs up, warnings; and Zoom In. */
export function showLogisticsDetails(node, side) {
    const data = node && node.logistics && node.logistics[side];
    if (!data) return hideLogisticsDetails();
    $('logistics-title').innerText = `${side === 'out' ? 'Output' : 'Input'} logistics: ${nodeLabel(node.id)}`;
    $('logistics-complexity').innerText = data.complexity;
    $('logistics-belts').innerText = data.belts.length;
    $('logistics-backed-up').innerText = data.backed_up > EPSILON ? `${data.backed_up.toFixed(2)}/min (buildings idle)` : 'nothing';
    $('logistics-edited').innerText = data.edited ? 'edited' : 'suggested';
    $('logistics-warnings').replaceChildren(...data.warnings.map(text => Object.assign(document.createElement('li'), { textContent: text })));
    const zoom = $('logistics-zoom-btn');
    zoom.dataset.node = node.id;
    zoom.dataset.side = side;
    $('logistics-details').style.display = 'block';
    updateNodeEmpty();
}

export function hideLogisticsDetails() {
    const section = $('logistics-details');
    if (section) section.style.display = 'none';
    updateNodeEmpty();
}

// --- Selected edge: its belts (ticket 041) ---

/** An edge's belts: how many, of what tier, and buttons to change how many. */
export function showEdgeDetails(edge) {
    if (!edge) return hideEdgeDetails();
    const name = id => id === 'External Demand' ? 'the demand' : id === 'sink' ? 'the Sink' : nodeLabel(id);
    $('edge-title').innerText = `${name(edge.producer)} → ${name(edge.consumer)}`;
    $('edge-item').innerText = edge.item;
    $('edge-rate').innerText = `${edge.rate.toFixed(2)}/min`;
    $('edge-belts').innerText = `${edge.count}× ${edge.kind === 'pipe' ? 'pipe ' : ''}Mk.${edge.tier}`;
    const needs = `The rate needs ${edge.needed} ${edge.kind}${edge.needed === 1 ? '' : 's'}.`;
    const over = edge.over ? ` ${edge.count} can't carry it: some backs up.` : '';
    $('edge-hint').innerText = edge.set
        ? `${needs}${over} Set by you: the belts are matched one by one with the layouts at both ends (zoom in on either).`
        : `${needs} Add belts to match them one by one with the layouts at both ends, e.g. a belt for each consumer building.`;
    ['edge-belt-more', 'edge-belt-fewer', 'edge-belt-default'].forEach(id => {
        $(id).dataset.key = edge.key;
        $(id).dataset.count = edge.count;
    });
    $('edge-belt-fewer').disabled = edge.count <= 1;
    $('edge-belt-more').disabled = edge.count >= 12;
    $('edge-belt-default').style.display = edge.set ? '' : 'none';
    $('edge-details').style.display = 'block';
    updateNodeEmpty();
}

export function hideEdgeDetails() {
    const section = $('edge-details');
    if (section) section.style.display = 'none';
    updateNodeEmpty();
}

// --- Selected by-product (an edge from its maker) ---

/** The maker's by-products: what's made, used and sunk, and a button to use them or send them to the Sink. */
export function showByproductDetails(maker) {
    if (!maker || !maker.byproducts || !maker.byproducts.length) return hideByproductDetails();
    const byproducts = maker.byproducts;
    const made = byproducts.reduce((sum, b) => sum + b.rate, 0);
    const used = byproducts.reduce((sum, b) => sum + Object.values(b.used).reduce((s, r) => s + r, 0), 0);
    const choice = byproducts[0].choice;

    $('byproduct-item').innerText = byproducts.map(b => b.item).join(', ');
    $('byproduct-maker').innerText = nodeLabel(maker.id);
    $('byproduct-maker').title = derivationText(maker.derivation || []);
    $('byproduct-rate').innerText = `${made.toFixed(2)}/min`;
    $('byproduct-used').innerText = `${used.toFixed(2)}/min`;
    $('byproduct-sunk').innerText = `${(made - used).toFixed(2)}/min`;

    const loop = byproducts.find(b => b.loop);
    const hints = [];
    if (choice === 'use' && loop) {
        hints.push('Using it would feed a node above its own maker (a loop), so it goes to the Sink. Solve Loop balances it.');
    } else if (choice === 'solve' && loop && !loop.settled) {
        hints.push(`The loop didn't settle in ${loop.rounds} rounds, so it goes to the Sink.`);
    } else if (choice === 'solve' && loop) {
        hints.push(`Loop solved (${loop.rounds} rounds).`);
    }
    if (choice !== 'sink' && made - used > EPSILON && !(loop && choice === 'use')) {
        hints.push('More is made than the plan needs; the rest goes to the Sink.');
    }
    if (byproducts.some(b => b.fluid) && made - used > EPSILON) hints.push("Fluids can't be sunk.");
    $('byproduct-hint').innerText = hints.join(' ');

    const button = $('byproduct-toggle-btn');
    button.innerText = choice === 'sink' ? 'Use as Supply' : 'Send to Sink';
    button.dataset.maker = maker.id;
    button.dataset.choice = choice === 'sink' ? 'use' : 'sink';
    // Solving is offered on loops only; "use" leaves a loop out
    const solve = $('byproduct-solve-btn');
    solve.style.display = loop ? 'block' : 'none';
    solve.innerText = choice === 'solve' ? 'Stop Solving' : 'Solve Loop';
    solve.dataset.maker = maker.id;
    solve.dataset.choice = choice === 'solve' ? 'use' : 'solve';
    $('byproduct-details').style.display = 'block';
    updateNodeEmpty();
}

export function hideByproductDetails() {
    $('byproduct-details').style.display = 'none';
    updateNodeEmpty();
}
