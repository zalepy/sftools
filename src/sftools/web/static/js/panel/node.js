// The Node tab's selected node: its recipe and stats, input breakdown, clocks, built marks and preferred recipe.
import { fetchRecipes } from '../api.js';
import { getNodeData } from '../graph.js';
import { clocksText, buildingsText, builtStatus, inboundUnused, generatorsText, burnedText } from '../node-info.js';
import { fitLastClock, clockGroups, clockBoxes } from '../clocks.js';
import { state } from '../state.js';
import { showNodeNote, pinNote } from '../notes.js';
import { $, EPSILON, updateNodeEmpty, nodeLabel, derivationText, statRow } from './common.js';
import { renderMoveBranch } from './move-branch.js';
import { defaultRecipe, ownRecipeNodes } from './recipes.js';

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
        : data.generators ? generatorsText(data)
        : clocks ? `${buildingsText(data)} (${clocks})` : buildingsText(data);
    $('detail-shards').innerText = data.power_shards || 0;
    $('detail-output-rate').innerText = parseFloat(data.throughput).toFixed(2) + '/min';
    $('detail-power').innerText = parseFloat(data.power).toFixed(2) + ' MW';

    const surplusEl = $('detail-surplus-value');
    if (data.sink) {
        // The Sink has no surplus; it flags what it can't take: fluids, and nuclear waste (ticket 057)
        const { fluids, waste = [] } = data.sink;
        const cant = [fluids.length && `Fluids can't be sunk: ${fluids.join(', ')}`,
            waste.length && `Nuclear waste can't be sunk: ${waste.join(', ')}`].filter(Boolean);
        surplusEl.innerText = cant.length ? cant.join('. ') : 'All by-products sunk';
        surplusEl.style.color = cant.length ? 'var(--status-shortage)' : 'var(--text-secondary)';
        $('detail-clock').innerText = '-';
        return;
    }
    if (data.generators) {
        // Generated power, the average the fuel gives; the last generators burn with gaps (tickets 055, 057)
        $('detail-output-rate').innerText = burnedText(data);
        surplusEl.innerText = `Underfed ones burn with gaps: ${data.generators.power.toFixed(2)} MW on average`;
        surplusEl.style.color = 'var(--text-secondary)';
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
            const row = statRow(`for ${nodeLabel(parentId)}:`, `${part.toFixed(2)}/min`, { className: 'breakdown-row' });
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

// Each fill of the recipe list; a response for an earlier one (another node, clicked before) is dropped
let recipeRequest = 0;

async function populateRecipeSelector(itemName, currentRecipeName) {
    const selector = $('recipe-select');
    selector.replaceChildren(new Option('Loading...', ''));
    selector.disabled = true;
    const request = ++recipeRequest;

    try {
        const recipes = await fetchRecipes(itemName);
        if (request !== recipeRequest) return;
        selector.replaceChildren(...recipes.map(r => new Option(
            `${r.name} (${r.type}${r.byproduct ? ', by-product' : ''})`,
            r.name,
            false,
            r.name === currentRecipeName
        )));
        selector.disabled = false;
    } catch (e) {
        if (request !== recipeRequest) return;
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
    const boxes = clockBoxes(state.clocks[data.id]);
    $('clock-all').value = boxes.all;
    $('clock-last').value = boxes.last;
    renderFitClock(data);
    // No buildings to clock on inbound production
    $('clock-controls').style.display = data.is_supplied ? 'none' : '';
    // Inbound production is set in the Inbound Production rows, not on the node; the Sink and the
    // Generators only receive, and the burn Refinery always runs Residual Fuel (ticket 055)
    const fixed = data.inbound || data.sink || data.generators || data.burn;
    $('details-recipe-collapsible').style.display = fixed ? 'none' : '';
    if (data.sink || data.generators) $('clock-controls').style.display = 'none';

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

export function hideNodeDetails() {
    $('node-details').style.display = 'none';
    state.selectedNodeId = null;
    updateNodeEmpty();
    pinNote(null);
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

// --- Clocks ---

function renderFitClock(data) {
    const button = $('fit-clock-btn');
    const fit = fitLastClock(data);
    button.disabled = Boolean(fit.why);
    button.title = fit.why || `Fit the last building to the demand: ${fit.count} building${fit.count === 1 ? '' : 's'}, the last at ${+(fit.clock * 100).toFixed(4)}%`;
}

/** Clock groups from the boxes, or null for the default (all at 100%). */
export function getClockInputs() {
    return clockGroups(parseFloat($('clock-all').value), parseFloat($('clock-last').value));
}

export function clearClockInputs() {
    $('clock-all').value = '';
    $('clock-last').value = '';
}

// --- Preferred recipes (ticket 043) ---

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
