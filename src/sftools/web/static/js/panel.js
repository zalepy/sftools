// Sidebar: demand rows, selected-node details, recipe picker, colors tab and the plan notice.
import { fetchRecipes } from './api.js';
import { getNodeData, clocksText, buildingsText } from './graph.js';
import { state } from './state.js';

const EPSILON = 0.0001;
const $ = id => document.getElementById(id);

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

// IDs are item paths ('Smart Plating__Rotor__Screws', see child_node_id), with '~n' for the parts
// of a split node: name a consumer by its item and the item it feeds, which tells apart several
// nodes making the same item.
function itemOf(segment) {
    return segment.replace(/~\d+$/, '');
}

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
    return path.length > 1 ? `${raw.output_item} (in ${itemOf(path.at(-2))})` : `${raw.output_item} (demand)`;
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
        : data.is_supplied ? 'None (supplied from outside)'
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
    if (Math.abs(surplus) < EPSILON) {
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

// Recipe name the server reads as "supplied from outside the plan" (calculator.OUTSIDE_SUPPLY)
const OUTSIDE_SUPPLY = 'Supplied from outside';

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
        )), new Option(`${OUTSIDE_SUPPLY} (no buildings or inputs)`, OUTSIDE_SUPPLY, false,
            currentRecipeName === OUTSIDE_SUPPLY));
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
    // No buildings to clock on a node supplied from outside
    $('clock-controls').style.display = data.is_supplied ? 'none' : '';
    // Inbound production is set in the Inbound Production rows, not on the node; the Sink only receives
    const fixed = data.inbound || data.sink;
    $('details-recipe-collapsible').style.display = fixed ? 'none' : '';
    $('split-controls').style.display = fixed ? 'none' : '';
    if (data.sink) $('clock-controls').style.display = 'none';

    // Unmerge is offered on merge targets
    const isMergeTarget = Object.values(state.merges).includes(data.id);
    $('unmerge-btn').style.display = isMergeTarget ? 'block' : 'none';

    renderSplit(data);
    if (!fixed) populateRecipeSelector(data.output_item, data.recipe_name || data.name);

    $('node-details').style.display = 'block';
}

// Merged nodes can't be split: which branch's demand would go to which part?
function renderSplit(data) {
    const merged = data.is_merged;
    $('split-count').value = data.split ? data.split.count : 2;
    $('split-count').disabled = merged;
    $('split-btn').disabled = merged;
    $('split-btn').textContent = data.split ? 'Set Parts' : 'Split';
    $('split-hint').textContent = merged
        ? 'Unmerge first to split this node.'
        : data.split
            ? `Part ${data.split.part} of ${data.split.count}. Each part has its own inputs, clocks and recipe.`
            : 'Equal parts, each with its own inputs, clocks and recipe.';
    $('unsplit-btn').style.display = data.split ? 'block' : 'none';
}

export function getSplitCount() {
    return parseInt($('split-count').value, 10);
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
}

export function hideByproductDetails() {
    $('byproduct-details').style.display = 'none';
}

export function hideNodeDetails() {
    $('node-details').style.display = 'none';
    state.selectedNodeId = null;
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

// --- Colors tab ---

export function renderColorList() {
    const container = $('color-list');
    container.replaceChildren(...Object.keys(state.colors).sort().map(item => {
        const row = document.createElement('div');
        row.className = 'color-item';

        const label = document.createElement('span');
        label.className = 'color-label';
        label.textContent = item;

        const wrapper = document.createElement('div');
        wrapper.className = 'color-input-wrapper';
        const input = document.createElement('input');
        input.type = 'color';
        input.className = 'color-input';
        input.value = state.colors[item];
        input.dataset.item = item;
        wrapper.appendChild(input);

        row.append(label, wrapper);
        return row;
    }));
}

export function readColorInputs() {
    const colors = {};
    document.querySelectorAll('.color-input').forEach(input => {
        colors[input.dataset.item] = input.value;
    });
    return colors;
}

// --- Collapsing the side panel ---

const PANEL_KEY = 'sf_planner_panel_collapsed';

/** Wires the header button; `onResize` runs after the graph area changes width. */
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
        li.textContent = `${entry.kind} on ${itemOf(entry.node_id.split('__').pop())}: ${entry.reason}`;
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
