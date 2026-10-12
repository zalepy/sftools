// Sidebar: demand rows, selected-node details, recipe picker, colors tab and the plan notice.
import { fetchRecipes } from './api.js';
import { getNodeData } from './graph.js';
import { state } from './state.js';

const EPSILON = 0.0001;
const $ = id => document.getElementById(id);

// --- Demand rows ---

const demandRows = $('demand-rows');

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

// Removing the last row only clears it
demandRows.addEventListener('click', e => {
    const button = e.target.closest('.remove-row');
    if (!button) return;
    const row = button.closest('.demand-row');
    if (demandRows.children.length > 1) {
        row.remove();
    } else {
        row.querySelectorAll('input').forEach(i => i.value = '');
    }
});

export function getDemands() {
    const items = [];
    const rates = [];
    demandRows.querySelectorAll('.demand-row').forEach(row => {
        const inputs = row.querySelectorAll('input');
        if (inputs[0].value && inputs[1].value) {
            items.push(inputs[0].value.trim());
            rates.push(parseFloat(inputs[1].value));
        }
    });
    return { items, rates };
}

export function setDemands(items = [], rates = []) {
    demandRows.replaceChildren();
    items.forEach((item, i) => demandRows.appendChild(createRow(item, rates[i])));
    if (items.length === 0) addRow();
}

export function getRoundUp() {
    return $('round-up-toggle').checked;
}

export function setRoundUp(value) {
    $('round-up-toggle').checked = value;
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

    $('detail-scale').innerText = buildingScale.toFixed(2) + 'x';
    $('detail-output-rate').innerText = parseFloat(data.throughput).toFixed(2) + '/min';
    $('detail-power').innerText = parseFloat(data.power).toFixed(2) + ' MW';

    const surplusEl = $('detail-surplus-value');
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

    // Clock speed per building to run at exactly the needed rate
    $('detail-clock').innerText = ((idealScale / buildingScale) * 100).toFixed(1) + '%';
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

    // The override box shows the override if there is one, otherwise the current scale
    const override = state.overrides[data.id];
    $('override-scale').value = override ? override : parseFloat(data.building_scale).toFixed(4);

    // Unmerge is offered on merge targets
    const isMergeTarget = Object.values(state.merges).includes(data.id);
    $('unmerge-btn').style.display = isMergeTarget ? 'block' : 'none';

    renderSplit(data);
    populateRecipeSelector(data.output_item, data.recipe_name || data.name);

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
            ? `Part ${data.split.part} of ${data.split.count}. Each part has its own inputs, override and recipe.`
            : 'Equal parts, each with its own inputs, override and recipe.';
    $('unsplit-btn').style.display = data.split ? 'block' : 'none';
}

export function getSplitCount() {
    return parseInt($('split-count').value, 10);
}

export function hideNodeDetails() {
    $('node-details').style.display = 'none';
    state.selectedNodeId = null;
}

export function getOverrideInput() {
    return parseFloat($('override-scale').value);
}

export function clearOverrideInput() {
    $('override-scale').value = '';
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
