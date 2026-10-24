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

/**
 * The maker's by-product `item` (all of them without it): what's made, used and sunk (or burned), buttons to
 * use it, burn it or send it to the Sink, and what can be made from it (`recipes`, [{name, product}], ticket 059).
 */
export function showByproductDetails(maker, item = null, recipes = []) {
    const all = (maker && maker.byproducts) || [];
    const byproducts = item ? all.filter(b => b.item === item) : all;
    if (!byproducts.length) return hideByproductDetails();
    const made = byproducts.reduce((sum, b) => sum + b.rate, 0);
    // Left over and burned: Heavy Oil Residue by the burn Refinery (ticket 055), a fuel by its generators (058)
    const burned = byproducts.reduce((sum, b) => sum + (b.burned || 0), 0);
    const used = byproducts.reduce((sum, b) => sum + Object.values(b.used).reduce((s, r) => s + r, 0), 0) - burned;
    const burns = byproducts.some(b => b.burn);
    const choice = byproducts[0].choice;
    const notUsed = choice === 'sink' || choice === 'burn';
    const solidFuel = byproducts.find(b => b.fuel && !b.fluid);

    $('byproduct-item').innerText = byproducts.map(b => b.item).join(', ');
    $('byproduct-maker').innerText = nodeLabel(maker.id);
    $('byproduct-maker').title = derivationText(maker.derivation || []);
    $('byproduct-rate').innerText = `${made.toFixed(2)}/min`;
    $('byproduct-used').innerText = `${used.toFixed(2)}/min`;
    $('byproduct-sunk-label').innerText = burns ? 'Burned for power:' : 'To the Sink:';
    $('byproduct-sunk').innerText = `${(made - used).toFixed(2)}/min`;

    const loop = byproducts.find(b => b.loop);
    const away = burns ? 'is burned for power' : 'goes to the Sink';
    const hints = [];
    if (choice === 'use' && loop) {
        hints.push(`Using it would feed a node above its own maker (a loop), so it ${away}. Solve Loop balances it.`);
    } else if (choice === 'solve' && loop && !loop.settled) {
        hints.push(`The loop didn't settle in ${loop.rounds} rounds, so it ${away}.`);
    } else if (choice === 'solve' && loop) {
        hints.push(`Loop solved (${loop.rounds} rounds).`);
    }
    if (!notUsed && made - used > EPSILON && !(loop && choice === 'use')) {
        hints.push(`More is made than the plan needs; the rest ${away}.`);
    }
    if (byproducts.some(b => b.fluid && !b.burn) && made - used > EPSILON) hints.push("Fluids can't be sunk.");
    // Nuclear waste (ticket 057) can't be sunk or used here; it's left over for the user to deal with
    const waste = byproducts.some(b => b.waste);
    if (waste) hints.push("Nuclear waste can't be sunk: store it, or make Plutonium from it in another plan.");
    if (solidFuel && !solidFuel.burn) hints.push("Sinking a fuel makes sense only for a while, e.g. until the generators' water is routed in.");
    $('byproduct-hint').innerText = hints.join(' ');

    // Use as Supply, or not: then a fuel is burned (ticket 058) and anything else goes to the Sink (residue: burned)
    // Choices are per by-product (ticket 059) when one was selected
    ['byproduct-toggle-btn', 'byproduct-sink-btn', 'byproduct-solve-btn', 'byproduct-make', 'byproduct-make-to']
        .forEach(id => { $(id).dataset.item = item || ''; });
    const button = $('byproduct-toggle-btn');
    button.innerText = notUsed ? 'Use as Supply' : burns ? 'Burn for Power' : 'Send to Sink';
    button.dataset.maker = maker.id;
    button.dataset.choice = notUsed ? 'use' : byproducts.some(b => b.fuel) ? 'burn' : 'sink';
    button.style.display = waste ? 'none' : '';
    // A solid fuel can also go to the Sink, for a while
    const sink = $('byproduct-sink-btn');
    sink.style.display = solidFuel ? 'block' : 'none';
    sink.innerText = solidFuel && !solidFuel.burn ? 'Burn for Power' : 'Send to Sink';
    sink.dataset.maker = maker.id;
    sink.dataset.choice = solidFuel && !solidFuel.burn ? 'burn' : 'sink';
    // Solving is offered on loops only; "use" leaves a loop out
    const solve = $('byproduct-solve-btn');
    solve.style.display = loop ? 'block' : 'none';
    solve.innerText = choice === 'solve' ? 'Stop Solving' : 'Solve Loop';
    solve.dataset.maker = maker.id;
    solve.dataset.choice = choice === 'solve' ? 'use' : 'solve';
    showMake(maker, item ? byproducts[0] : null, recipes);
    $('byproduct-details').style.display = 'block';
    updateNodeEmpty();
}

/** Make from it (ticket 059): the recipes that take the by-product, and where what's made goes. */
function showMake(maker, byproduct, recipes) {
    $('byproduct-make-group').style.display = byproduct && recipes.length ? 'block' : 'none';
    if (!byproduct) return;
    const select = $('byproduct-make');
    select.replaceChildren(new Option('Nothing', ''), ...recipes.map(r => new Option(`${r.product} (${r.name})`, r.name)));
    select.value = byproduct.make ? byproduct.make.recipe : '';
    select.dataset.maker = maker.id;
    const to = $('byproduct-make-to');
    to.value = byproduct.make ? byproduct.make.to : 'supply';
    to.disabled = !byproduct.make;
    to.dataset.maker = maker.id;
    if (byproduct.make) {
        const hint = $('byproduct-hint');
        hint.innerText = [hint.innerText, `What's left goes to ${byproduct.make.recipe}.`].filter(Boolean).join(' ');
    }
}

export function hideByproductDetails() {
    $('byproduct-details').style.display = 'none';
    updateNodeEmpty();
}
