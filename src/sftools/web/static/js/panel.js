// Sidebar: demand rows, selected-node details, recipe picker, colors and recipes tabs, and the plan notice.
import { fetchRecipes } from './api.js';
import { getNodeData, allNodeData, clocksText, buildingsText, builtStatus, inboundUnused } from './graph.js';
import { state } from './state.js';
import { showNodeNote, pinNote } from './notes.js';

const EPSILON = 0.0001;
const $ = id => document.getElementById(id);

// --- Tabs ---

/** Shows a tab of the side panel: 'planner', 'node', 'colors' or 'recipes'. */
export function showTab(tabId) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab.dataset.tab === tabId));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.toggle('active', content.id === `${tabId}-tab`));
}

// The Node tab says what to click while nothing is selected
function updateNodeEmpty() {
    const shown = ['node-details', 'byproduct-details', 'edge-details', 'logistics-details']
        .some(id => $(id) && $(id).style.display === 'block');
    $('node-empty').hidden = shown;
}

// --- Demand and inbound rows ---

const demandRows = $('demand-rows');
const inboundRows = $('inbound-rows');

function createRow(item = '', rate = '') {
    const row = document.createElement('div');
    row.className = 'demand-row';

    const itemInput = document.createElement('input');
    itemInput.type = 'text';
    itemInput.name = 'items';
    itemInput.setAttribute('list', 'items_list');
    itemInput.placeholder = 'Item';
    itemInput.value = item;

    const rateInput = document.createElement('input');
    rateInput.type = 'number';
    rateInput.step = 'any';
    rateInput.name = 'rates';
    rateInput.placeholder = 'Rate';
    rateInput.value = rate;

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'secondary remove-row';
    remove.style.width = 'auto';
    remove.textContent = '✕';

    row.append(itemInput, rateInput, remove);
    return row;
}

export function addRow() {
    demandRows.appendChild(createRow());
}

export function addInboundRow() {
    inboundRows.appendChild(createRow());
}

// Removing the last row only clears it
[demandRows, inboundRows].forEach(rows => rows.addEventListener('click', e => {
    const button = e.target.closest('.remove-row');
    if (!button) return;
    const row = button.closest('.demand-row');
    if (rows.children.length > 1) {
        row.remove();
    } else {
        row.querySelectorAll('input').forEach(i => i.value = '');
    }
}));

/** Filled-in rows as [{item, rate}]. */
function readRows(rows) {
    const entries = [];
    rows.querySelectorAll('.demand-row').forEach(row => {
        const inputs = row.querySelectorAll('input');
        if (inputs[0].value && inputs[1].value) {
            entries.push({ item: inputs[0].value.trim(), rate: parseFloat(inputs[1].value) });
        }
    });
    return entries;
}

function fillRows(rows, entries) {
    rows.replaceChildren(...entries.map(({ item, rate }) => createRow(item, rate)));
    if (entries.length === 0) rows.appendChild(createRow());
}

/** Demand targets as items and rates, and inbound production as [{item, rate}]. */
export function getDemands() {
    const demands = readRows(demandRows);
    return { items: demands.map(d => d.item), rates: demands.map(d => d.rate), inbound: readRows(inboundRows) };
}

export function setDemands(items = [], rates = [], inbound = []) {
    fillRows(demandRows, items.map((item, i) => ({ item, rate: rates[i] })));
    fillRows(inboundRows, inbound);
}


// --- Selected node ---

// IDs are item paths ('Smart Plating__Rotor__Screws', see child_node_id): name a consumer by its item
// and the item it feeds, which tells apart several nodes making the same item.

/** One line per step, e.g. "Reinforced Iron Plate ← Alternate: Bolted Iron Plate (Assembler)". */
export function derivationText(derivation) {
    return derivation.map(step => `${step.item} ← ${step.recipe} (${step.building})`).join('\n');
}

function derivationList(derivation) {
    const list = document.createElement('ol');
    list.className = 'derivation';
    list.replaceChildren(...derivation.map(step => {
        const li = document.createElement('li');
        const item = document.createElement('span');
        item.className = 'item';
        item.textContent = step.item;
        li.append(item, ` ← ${step.recipe} (${step.building})`);
        li.title = step.id;
        return li;
    }));
    return list;
}

function renderDerivation(data) {
    $('detail-derivation').replaceWith(Object.assign(derivationList(data.derivation || []), { id: 'detail-derivation' }));

    const merged = data.constituent_derivations || [];
    $('detail-merged-row').style.display = merged.length ? 'flex' : 'none';
    $('detail-merged').replaceChildren(...merged.map(derivationList));
}

function parentLabel(parentId) {
    if (parentId === 'External Demand') return 'External Demand';
    const raw = getNodeData(parentId);
    if (!raw) return parentId;
    const path = parentId.split('__');
    return path.length > 1 ? `${raw.output_item} (in ${path.at(-2)})` : `${raw.output_item} (demand)`;
}

function statRow(label, value, { className = 'stat-row', style = '' } = {}) {
    const row = document.createElement('div');
    row.className = className;
    if (style) row.style.cssText = style;
    const labelEl = document.createElement('span');
    const valueEl = document.createElement('span');
    if (className === 'stat-row') {
        labelEl.className = 'stat-label';
        valueEl.className = 'stat-value';
    }
    labelEl.textContent = label;
    valueEl.textContent = value;
    row.append(labelEl, valueEl);
    return row;
}

function renderBaseRecipe(data) {
    const container = $('base-recipe-details');
    container.replaceChildren();

    const heading = document.createElement('strong');
    heading.textContent = '100% Rate:';
    container.append(heading, document.createElement('br'),
        `${parseFloat(data.base_output_rate).toFixed(2)}/min ${data.output_item}`, document.createElement('br'));

    if (data.base_inputs && data.base_inputs.length > 0) {
        const inputsHeading = document.createElement('div');
        inputsHeading.style.marginTop = '0.4rem';
        const strong = document.createElement('strong');
        strong.textContent = 'Inputs (100%):';
        inputsHeading.appendChild(strong);
        container.appendChild(inputsHeading);
        data.base_inputs.forEach((inp, i) => {
            if (i > 0) container.appendChild(document.createElement('br'));
            container.append(`${parseFloat(inp.rate).toFixed(2)}/min ${inp.item}`);
        });
    }
}

function renderStats(data) {
    const buildingScale = parseFloat(data.building_scale);
    const idealScale = parseFloat(data.ideal_building_scale);
    const surplus = buildingScale - idealScale;

    const clocks = clocksText(data);
    $('detail-buildings').innerText = data.inbound ? `None (inbound, ${parseFloat(data.inbound.rate).toFixed(2)}/min available)`
        : clocks ? `${buildingsText(data)} (${clocks})` : buildingsText(data);
    $('detail-shards').innerText = data.power_shards || 0;
    $('detail-output-rate').innerText = parseFloat(data.throughput).toFixed(2) + '/min';
    $('detail-power').innerText = parseFloat(data.power).toFixed(2) + ' MW';

    const surplusEl = $('detail-surplus-value');
    if (data.sink) {
        // The Sink has no surplus; it flags what it can't take
        const fluids = data.sink.fluids;
        surplusEl.innerText = fluids.length ? `Fluids can't be sunk: ${fluids.join(', ')}` : 'All by-products sunk';
        surplusEl.style.color = fluids.length ? 'var(--status-shortage)' : 'var(--text-secondary)';
        $('detail-clock').innerText = '-';
        return;
    }
    if (data.inbound) {
        const unused = inboundUnused(data);
        surplusEl.innerText = unused > EPSILON ? `+${unused.toFixed(2)}/min unused` : 'All used';
        surplusEl.style.color = unused > EPSILON ? 'var(--status-surplus)' : 'var(--text-secondary)';
    } else if (Math.abs(surplus) < EPSILON) {
        surplusEl.innerText = 'Perfect Match';
        surplusEl.style.color = 'var(--text-secondary)';
    } else {
        const itemSurplus = surplus * parseFloat(data.base_output_rate);
        const sign = surplus > 0 ? '+' : '';
        surplusEl.innerText = `${sign}${surplus.toFixed(2)} bldgs (${sign}${itemSurplus.toFixed(2)}/min)`;
        surplusEl.style.color = surplus > EPSILON ? 'var(--status-surplus)' : 'var(--status-shortage)';
        if (surplus > 1 - EPSILON) surplusEl.style.color = 'var(--status-excessive)';
    }

    // Clock at which this many buildings would make exactly what's needed
    const buildings = parseFloat(data.buildings) || buildingScale;
    $('detail-clock').innerText = data.is_supplied ? '-' : ((idealScale / buildings) * 100).toFixed(1) + '%';
}

// Each input, broken down by which consumer of this node's output it is for
function renderScaledInputs(data) {
    const container = $('detail-inputs-container');
    container.replaceChildren();
    if (!data.scaled_inputs || data.scaled_inputs.length === 0) {
        container.style.display = 'none';
        return;
    }
    container.style.display = 'block';

    const totalOutput = parseFloat(data.throughput);
    const parentDemands = data.parent_demands || {};

    data.scaled_inputs.forEach(input => {
        const totalInputRate = parseFloat(input.rate);

        const details = document.createElement('details');
        details.style.marginBottom = '0.5rem';
        const summary = document.createElement('summary');
        summary.style.cssText = 'list-style: none; padding: 0; display: block;';
        summary.appendChild(statRow(`${input.item}:`, `${totalInputRate.toFixed(2)}/min`,
            { style: 'margin-bottom: 0; cursor: pointer;' }));
        details.appendChild(summary);

        const breakdown = document.createElement('div');
        breakdown.className = 'breakdown-list';
        let sumDemand = 0;
        for (const [parentId, rate] of Object.entries(parentDemands)) {
            const part = totalOutput > 0 ? totalInputRate * (rate / totalOutput) : 0;
            const row = statRow(`for ${parentLabel(parentId)}:`, `${part.toFixed(2)}/min`, { className: 'breakdown-row' });
            const parent = getNodeData(parentId);
            if (parent && parent.derivation) row.title = derivationText(parent.derivation);
            breakdown.appendChild(row);
            sumDemand += rate;
        }

        const surplusDemand = totalOutput - sumDemand;
        if (surplusDemand > EPSILON) {
            const part = totalOutput > 0 ? totalInputRate * (surplusDemand / totalOutput) : totalInputRate;
            breakdown.appendChild(statRow('Override/Surplus:', `${part.toFixed(2)}/min`, { className: 'breakdown-row' }));
        }

        details.appendChild(breakdown);
        container.appendChild(details);
    });
}

async function populateRecipeSelector(itemName, currentRecipeName) {
    const selector = $('recipe-select');
    selector.replaceChildren(new Option('Loading...', ''));
    selector.disabled = true;

    try {
        const recipes = await fetchRecipes(itemName);
        selector.replaceChildren(...recipes.map(r => new Option(
            `${r.name} (${r.type}${r.byproduct ? ', by-product' : ''})`,
            r.name,
            false,
            r.name === currentRecipeName
        )));
        selector.disabled = false;
    } catch (e) {
        console.error("Failed to fetch recipes", e);
        selector.replaceChildren(new Option('Error loading', ''));
    }
}

export function showNodeDetails(data) {
    state.selectedNodeId = data.id;

    $('detail-item').innerText = data.output_item;
    $('detail-recipe').innerText = data.recipe_name || data.name;
    $('detail-building').innerText = data.building;

    $('detail-id').innerText = data.id;
    $('detail-parents').innerText = data.parents.length > 0 ? data.parents.join(', ') : 'None';
    $('detail-children').innerText = data.children.length > 0 ? data.children.join(', ') : 'None';

    renderDerivation(data);
    renderBaseRecipe(data);
    renderStats(data);
    renderScaledInputs(data);

    // The clock boxes show the node's own settings; empty means the default
    const groups = state.clocks[data.id] || [];
    const rest = groups.find(g => g.count === undefined);
    const last = groups.find(g => g.count !== undefined);
    $('clock-all').value = rest && rest.clock !== 1 ? +(rest.clock * 100).toFixed(4) : '';
    $('clock-last').value = last ? +(last.clock * 100).toFixed(4) : '';
    renderFitClock(data);
    // No buildings to clock on inbound production
    $('clock-controls').style.display = data.is_supplied ? 'none' : '';
    // Inbound production is set in the Inbound Production rows, not on the node; the Sink only receives
    const fixed = data.inbound || data.sink;
    $('details-recipe-collapsible').style.display = fixed ? 'none' : '';
    if (data.sink) $('clock-controls').style.display = 'none';

    // Unmerge is offered on merge targets
    const isMergeTarget = Object.values(state.merges).includes(data.id);
    $('unmerge-btn').style.display = isMergeTarget ? 'block' : 'none';

    renderBuilt(data);
    renderMoveBranch(fixed ? null : data);
    if (!fixed) populateRecipeSelector(data.output_item, data.recipe_name || data.name);
    renderPreferred(fixed ? null : data);
    showNodeNote(data);

    $('node-details').style.display = 'block';
    updateNodeEmpty();
    pinNote(data.id);
}

// --- Move Branch to Inbound (ticket 045) ---

export const NEW_TAB = 'new';

/** What the node's consumers take: the rate that becomes inbound production. */
export function branchRate(data) {
    return Object.values(data.parent_demands || {}).reduce((sum, rate) => sum + rate, 0);
}

/** Why the node's branch can't be moved, or null: the item must be made by this node alone, and not be a demand target. */
function moveBlocked(data) {
    const item = data.output_item;
    if (getDemands().items.includes(item)) return `${item} is a demand target of this plan.`;
    const makers = allNodeData().filter(n => n.output_item === item && !n.inbound && !n.sink).length;
    if (makers > 1) return `Merge all ${makers} ${item} nodes first.`;
    return null;
}

/** By-products made in the node's branch that the rest of the plan uses as supply. */
function byproductsUsedElsewhere(data) {
    const branch = new Set();
    const stack = [data.id];
    while (stack.length) {
        const id = stack.pop();
        const node = getNodeData(id);
        if (branch.has(id) || !node || node.inbound) continue;
        branch.add(id);
        stack.push(...node.children);
    }
    const items = new Set();
    branch.forEach(id => (getNodeData(id).byproducts || []).forEach(b => {
        if (Object.keys(b.used || {}).some(consumer => !branch.has(consumer))) items.add(b.item);
    }));
    return [...items].sort();
}

function renderMoveBranch(data) {
    $('move-branch').style.display = data ? '' : 'none';
    $('move-branch-form').hidden = true;
    if (!data) return;
    const why = moveBlocked(data);
    $('move-branch-btn').disabled = Boolean(why);
    $('move-branch-why').innerText = why || '';
}

/** Opens the destination picker: Undefined, the other tabs, or a new tab. */
export function openMoveBranch(tabs, activeId) {
    const data = getNodeData(state.selectedNodeId);
    if (!data) return;
    const select = $('move-branch-dest');
    select.replaceChildren(
        new Option('Undefined (add the demand target later)', ''),
        ...tabs.filter(t => t.id !== activeId).map(t => new Option(t.name, t.id)),
        new Option('New tab…', NEW_TAB)
    );
    const rate = branchRate(data);
    const used = byproductsUsedElsewhere(data);
    const describe = () => {
        const lines = [`${rate.toFixed(2)}/min ${data.output_item} becomes inbound production here; this node and its inputs go.`];
        if (used.length) lines.push(`By-products of this branch used as supply elsewhere in this plan: ${used.join(', ')}. Those nodes grow.`);
        if (select.value) lines.push(`The destination gets a demand target of ${rate.toFixed(2)}/min, linked on the Chain tab. Undo here doesn't remove it.`);
        $('move-branch-info').innerText = lines.join('\n');
    };
    select.onchange = describe;
    describe();
    $('move-branch-form').hidden = false;
}

export function closeMoveBranch() {
    $('move-branch-form').hidden = true;
}

export function moveBranchDestination() {
    return $('move-branch-dest').value;
}

/** How many of the node's buildings are built (ticket 037); hidden on nodes without buildings. */
export function renderBuilt(data) {
    const status = builtStatus(data);
    $('built-controls').style.display = status ? '' : 'none';
    if (!status) return;
    $('built-count').value = status.built || '';
    $('built-of').innerText = `of ${status.needed}`;
    const button = $('built-all-btn');
    button.innerText = status.done ? 'Not Built' : 'All Built';
    button.dataset.count = status.done ? 0 : status.needed;
    $('built-hint').innerText = status.stale
        ? `${status.stale.count} were marked built for ${status.stale.recipe}; this node now runs ${data.recipe_name}.`
        : status.built > status.needed ? `${status.built - status.needed} more than the plan needs.`
        : status.built > 0 && !status.done ? `${status.needed - status.built} left to build.` : '';
}

export function getBuiltCount() {
    const count = parseInt($('built-count').value, 10);
    return isNaN(count) || count < 0 ? 0 : count;
}


// --- Selected logistics node (logistics mode) ---

/** A production node by name, as in the input breakdown: e.g. "Screws (in Rotor)". */
export function nodeLabel(nodeId) {
    return parentLabel(nodeId);
}

/** Summary of one side's logistics: splitters and mergers, belts, what backs up, warnings; and Zoom In. */
export function showLogisticsDetails(node, side) {
    const data = node && node.logistics && node.logistics[side];
    if (!data) return hideLogisticsDetails();
    $('logistics-title').innerText = `${side === 'out' ? 'Output' : 'Input'} logistics: ${parentLabel(node.id)}`;
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
    const name = id => id === 'External Demand' ? 'the demand' : id === 'sink' ? 'the Sink' : parentLabel(id);
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
    $('byproduct-maker').innerText = parentLabel(maker.id);
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

export function hideNodeDetails() {
    $('node-details').style.display = 'none';
    state.selectedNodeId = null;
    updateNodeEmpty();
    pinNote(null);
}

// --- Fit the last building to the demand (ticket 047) ---

const AVOIDED_COUNTS = [5, 7];  // hard to balance: one fewer building with up to 2 shards is better

/**
 * The clocks that make exactly the demand, with All at 100% and only the last building clocked:
 * {count, clock, groups}, or {why} when there's nothing to fit. One building fewer with the last at up
 * to 150% (1 shard) is preferred, then the buildings needed with the last underclocked; 5 and 7
 * buildings are avoided, by one fewer with the last at up to 200% (2 shards).
 */
export function fitLastClock(data) {
    const need = parseFloat(data.ideal_building_scale);  // buildings at 100%
    if (!(need > 0)) return { why: 'Nothing is demanded from this node.' };
    if (parseFloat(data.building_scale) - need <= EPSILON) return { why: 'No surplus to fit.' };
    const all = Math.ceil(need - 0.00001);
    const lastClock = count => need - (count - 1);
    const fits = (count, max) => count >= 1 && lastClock(count) <= max + 1e-9;
    const avoided = count => AVOIDED_COUNTS.includes(count);
    let count;
    if (!avoided(all - 1) && fits(all - 1, 1.5)) count = all - 1;
    else if (!avoided(all)) count = all;
    else if (fits(all - 1, 2)) count = all - 1;
    else count = all;
    // Under 1% (the lowest clock) the surplus is tiny: one fewer building, just over 100%
    if (lastClock(count) < 0.01) {
        if (!fits(all - 1, 2.5)) return { why: 'The surplus is too small to fit.' };
        count = all - 1;
    }
    // Rounded up to 4 decimals of a percent, so the node is never short
    const clock = Math.ceil(lastClock(count) * 1e6 - 1e-6) / 1e6;
    if (Math.abs(clock - 1) < 1e-9) return { why: 'No surplus to fit.' };
    return { count, clock, groups: [{ clock: 1 }, { count: 1, clock }] };
}

function renderFitClock(data) {
    const button = $('fit-clock-btn');
    const fit = fitLastClock(data);
    button.disabled = Boolean(fit.why);
    button.title = fit.why || `Fit the last building to the demand: ${fit.count} building${fit.count === 1 ? '' : 's'}, the last at ${+(fit.clock * 100).toFixed(4)}%`;
}

/** Clock groups from the boxes (percent), or null for the default (all at 100%). */
export function getClockInputs() {
    const all = parseFloat($('clock-all').value);
    const last = parseFloat($('clock-last').value);
    const allClock = isNaN(all) ? 1 : all / 100;
    const groups = [{ clock: allClock }];
    if (!isNaN(last) && last / 100 !== allClock) groups.push({ count: 1, clock: last / 100 });
    return groups.length === 1 && allClock === 1 ? null : groups;
}

export function clearClockInputs() {
    $('clock-all').value = '';
    $('clock-last').value = '';
}

// --- Preferred recipes (ticket 043) ---

/** Nodes of `item` in the plan shown that run a recipe of their own, other than the preferred one. */
export function ownRecipeNodes(item) {
    return Object.entries(state.recipes)
        .filter(([id, recipe]) => getNodeData(id)?.output_item === item && recipe !== state.preferred[item])
        .map(([id]) => id);
}

/** Prefer / Use Default Recipe for the node's item, and what's preferred now. */
function renderPreferred(data) {
    const recipe = data && (data.recipe_name || data.name);
    $('preferred-controls').style.display = recipe ? '' : 'none';
    if (!recipe) return;
    const item = data.output_item;
    const preferred = state.preferred[item];
    const own = ownRecipeNodes(item).length;
    const keep = own ? ` ${own} node${own === 1 ? '' : 's'} here keep${own === 1 ? 's' : ''} a recipe of ${own === 1 ? 'its' : 'their'} own.` : '';
    $('prefer-btn').textContent = `Prefer for ${item}`;
    // Nothing to prefer when the node runs the default and nothing else is preferred
    $('prefer-btn').style.display = preferred === recipe || (!preferred && recipe === defaultRecipe(item)) ? 'none' : '';
    $('unprefer-btn').style.display = preferred ? '' : 'none';
    $('preferred-hint').innerText = preferred === recipe
        ? `Preferred for ${item}: new ${item} nodes run it, in every tab.${keep}`
        : preferred
            ? `Preferred for ${item}: ${preferred}.${keep}`
            : recipe === defaultRecipe(item)
                ? `${item} nodes run this recipe (the default) unless switched. Pick another for all of them on the Recipes tab.`
                : `${item} nodes run the default recipe unless switched. Prefer this one to run it in every ${item} node, in every tab.`;
}

// The Recipes tab: every item made by more than one recipe, with a dropdown of its recipes
let recipeChoices = [];  // from the server: [{item, default, recipes}]
let onRecipeChange = null;  // (item, recipe or null for the default)

export function initRecipeList(choices, onChange) {
    recipeChoices = choices;
    onRecipeChange = onChange;
    $('recipe-filter').addEventListener('input', filterRecipeList);
    $('recipe-changed-only').addEventListener('change', filterRecipeList);
    renderRecipeList();
}

/** The recipe an item's nodes run by default, or null when it has no other. */
export function defaultRecipe(item) {
    return recipeChoices.find(choice => choice.item === item)?.default ?? null;
}

/** Redraws the Recipes tab from the preferred recipes. */
export function renderRecipeList() {
    $('recipe-list').replaceChildren(...recipeChoices.map(choice => {
        const preferred = choice.recipes.some(r => r.name === state.preferred[choice.item]) ? state.preferred[choice.item] : choice.default;
        const row = document.createElement('div');
        row.className = `recipe-choice${preferred === choice.default ? '' : ' changed'}`;
        row.dataset.item = choice.item;
        const label = Object.assign(document.createElement('span'), { textContent: choice.item });
        const select = document.createElement('select');
        select.setAttribute('aria-label', `Preferred recipe for ${choice.item}`);
        select.replaceChildren(...choice.recipes.map(r => new Option(
            `${r.name}${r.name === choice.default ? ' (default)' : r.byproduct ? ' (by-product)' : ''}`, r.name, false, r.name === preferred)));
        select.addEventListener('change', () => onRecipeChange(choice.item, select.value === choice.default ? null : select.value));
        row.append(label, select);
        return row;
    }));
    filterRecipeList();
}

function filterRecipeList() {
    const text = $('recipe-filter').value.trim().toLowerCase();
    const changedOnly = $('recipe-changed-only').checked;
    document.querySelectorAll('#recipe-list .recipe-choice').forEach(row => {
        row.hidden = (text && !row.dataset.item.toLowerCase().includes(text)) || (changedOnly && !row.classList.contains('changed'));
    });
}

// --- Colors tab ---

/**
 * The colored items, with the unsaved edits in `colors` (Save Colors keeps them). × on a built-in item
 * puts its built-in color back; on an item the user defined, it drops the row.
 */
export function renderColorList(colors = state.colors) {
    const container = $('color-list');
    container.replaceChildren(...Object.keys(colors).sort().map(item => {
        const row = document.createElement('div');
        row.className = 'color-item';
        row.dataset.item = item;

        const label = document.createElement('span');
        label.className = 'color-label';
        label.textContent = item;

        const wrapper = document.createElement('div');
        wrapper.className = 'color-input-wrapper';
        const input = document.createElement('input');
        input.type = 'color';
        input.className = 'color-input';
        input.value = colors[item];
        input.dataset.item = item;

        const builtIn = state.defaultColors[item];
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'color-remove';
        remove.textContent = '×';
        remove.title = builtIn ? `Reset to the built-in color (${builtIn})` : 'Remove';
        remove.addEventListener('click', () => {
            if (builtIn) {
                input.value = builtIn;
            } else {
                row.remove();
            }
        });
        wrapper.append(input, remove);

        row.append(label, wrapper);
        return row;
    }));
}

export function readColorInputs() {
    const colors = {};
    document.querySelectorAll('#color-list .color-input').forEach(input => {
        colors[input.dataset.item] = input.value;
    });
    return colors;
}

/** Wires Define: adds the item with the picked color to the list (or recolors it if it's there). */
export function initColorDefine() {
    const itemInput = $('color-add-item');
    const error = $('color-add-error');
    const items = new Set([...document.querySelectorAll('#items_list option')].map(o => o.value));

    function define() {
        const item = itemInput.value.trim();
        error.hidden = items.has(item);
        if (!items.has(item)) {
            error.textContent = item ? `Unknown item: ${item}` : 'Pick an item first.';
            return;
        }
        renderColorList({ ...readColorInputs(), [item]: $('color-add-value').value });
        itemInput.value = '';
        colorRow(item)?.scrollIntoView({ block: 'nearest' });
    }

    $('color-add-btn').addEventListener('click', define);
    itemInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            define();
        }
    });
}

function colorRow(item) {
    return [...document.querySelectorAll('#color-list .color-item')].find(row => row.dataset.item === item);
}

// --- Collapsing the side panel ---

const PANEL_KEY = 'sf_planner_panel_collapsed';
const LEGEND_KEY = 'sf_legend_shown';

/** Wires the header button; `onResize` runs after the graph area changes width. */
/**
 * The legend (ticket 035): shown or hidden with the header button, remembered in the browser.
 * `opened` runs when it opens (the guide closes); returns { hide }.
 */
export function initLegendToggle({ opened = () => {} } = {}) {
    const button = $('legend-toggle');
    const legend = $('legend');

    function setShown(shown) {
        legend.hidden = !shown;
        button.setAttribute('aria-expanded', String(shown));
        button.title = shown ? 'Hide the legend' : 'Show the legend';
        button.classList.toggle('active', shown);
    }

    let shown = false;
    try {
        shown = localStorage.getItem(LEGEND_KEY) === '1';
    } catch (e) {
        // Storage unavailable: start hidden
    }
    setShown(shown);

    function remember() {
        try {
            localStorage.setItem(LEGEND_KEY, shown ? '1' : '0');
        } catch (e) {
            // Not remembered; the legend still toggles
        }
    }

    button.addEventListener('click', () => {
        shown = legend.hidden;
        if (shown) opened();
        setShown(shown);
        remember();
    });
    return {
        hide() {
            if (!shown) return;
            shown = false;
            setShown(false);
            remember();
        }
    };
}

export function initPanelToggle(onResize) {
    const button = $('panel-toggle');
    const container = document.querySelector('.main-container');

    function setCollapsed(collapsed) {
        container.classList.toggle('panel-collapsed', collapsed);
        button.setAttribute('aria-expanded', String(!collapsed));
        button.title = collapsed ? 'Show side panel' : 'Hide side panel';
        button.innerHTML = collapsed ? '&#x276F;' : '&#x276E;';
        onResize();
    }

    let collapsed = false;
    try {
        collapsed = localStorage.getItem(PANEL_KEY) === '1';
    } catch (e) {
        // Storage unavailable: start expanded
    }
    setCollapsed(collapsed);

    button.addEventListener('click', () => {
        collapsed = !container.classList.contains('panel-collapsed');
        setCollapsed(collapsed);
        try {
            localStorage.setItem(PANEL_KEY, collapsed ? '1' : '0');
        } catch (e) {
            // Not remembered; the panel still toggles
        }
    });
}

// --- Toast: a short, non-blocking message ---

let toastTimer = null;

export function showToast(text, ms = 4000) {
    const toast = $('toast');
    toast.textContent = text;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, ms);
}

// --- Plan notice (entries the server ignored) ---

let noticeTimer = null;

export function showPlanNotice(ignored) {
    const notice = $('plan-notice');
    const count = ignored.length;
    notice.querySelector('.plan-notice-text').textContent =
        `${count} saved adjustment${count === 1 ? '' : 's'} no longer match${count === 1 ? 'es' : ''} this plan and ${count === 1 ? 'was' : 'were'} removed.`;
    notice.querySelector('ul').replaceChildren(...ignored.map(entry => {
        const li = document.createElement('li');
        li.textContent = `${entry.kind} on ${entry.node_id.split('__').pop()}: ${entry.reason}`;
        li.title = entry.node_id;
        return li;
    }));
    notice.hidden = false;
    clearTimeout(noticeTimer);
    noticeTimer = setTimeout(hidePlanNotice, 15000);
}

export function hidePlanNotice() {
    $('plan-notice').hidden = true;
}

$('plan-notice').querySelector('.close').addEventListener('click', hidePlanNotice);
