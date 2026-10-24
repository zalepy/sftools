// Actions on the selected node: clocks, recipe, merges, built marks, by-products, and moving its branch.
import * as api from '../api.js';
import { state } from '../state.js';
import { refreshBuilt, getNodeData, reselectNode } from '../graph.js';
import * as tabs from '../tabs.js';
import { refreshChain, addLink } from '../chain.js';
import { fitLastClock } from '../clocks.js';
import { getDemands, setDemands } from '../panel/planner.js';
import { getClockInputs, clearClockInputs, hideNodeDetails, renderBuilt } from '../panel/node.js';
import { NEW_TAB, branchRate } from '../panel/move-branch.js';
import { showByproductDetails, hideByproductDetails } from '../panel/selection.js';
import { showToast } from '../panel/messages.js';
import { save, render, requestPlan, emptyPlan } from './plan.js';
import { notedRecipes, noteRecipeChanges } from './notes.js';

// --- Clocks ---

async function setClocks(groups) {
    const nodeId = state.selectedNodeId;
    if (!nodeId) return;
    const clocks = { ...state.clocks };
    if (groups) clocks[nodeId] = groups; else delete clocks[nodeId];
    try {
        render(await requestPlan({ clocks }));
        state.clocks = clocks;
        save();
        reselectNode(nodeId);
    } catch (e) {
        console.error("Clock change failed", e);
        alert(`Clock change failed: ${e.message}`);
    }
}

export function applyClocks() {
    setClocks(getClockInputs());
}

/** Sets the last building's clock so the node makes just what's demanded (ticket 047). */
export function fitClock() {
    const data = getNodeData(state.selectedNodeId);
    if (!data) return;
    const fit = fitLastClock(data);
    if (fit.groups) setClocks(fit.groups);
}

export function clearClocks() {
    clearClockInputs();
    setClocks(null);
}

// --- Recipe, merges, built marks, by-products ---

export async function switchRecipe(recipeName) {
    const nodeId = state.selectedNodeId;
    if (!recipeName || !nodeId) return;

    const recipes = { ...state.recipes, [nodeId]: recipeName };
    const before = notedRecipes();
    try {
        render(await requestPlan({ recipes }));
        state.recipes = recipes;
        noteRecipeChanges(before);
        save();
        reselectNode(nodeId);
    } catch (e) {
        console.error("Recipe switch failed", e);
        alert(`Recipe switch failed: ${e.message}`);
    }
}

export async function mergeNodes(sourceId, targetId) {
    // Flattening: anything merged into the source now points at the target
    const merges = { ...state.merges };
    for (const id in merges) {
        if (merges[id] === sourceId) merges[id] = targetId;
    }
    merges[sourceId] = targetId;

    // The merged node runs on the target's clocks
    const clocks = { ...state.clocks };
    delete clocks[sourceId];

    // Allowed, but worth a heads-up: the merged node runs the target's recipe
    const source = getNodeData(sourceId);
    const target = getNodeData(targetId);
    const recipesDiffer = source && target && source.recipe_name !== target.recipe_name;

    try {
        render(await requestPlan({ merges, clocks }));
        state.merges = merges;
        state.clocks = clocks;
        save();
        if (recipesDiffer) {
            showToast(`Merged nodes with different recipes: ${source.recipe_name} into ${target.recipe_name}. The merged node runs ${target.recipe_name}.`);
        }
    } catch (e) {
        console.error("Merge failed", e);
        alert(`Merge failed: ${e.message}`);
    }
}

export async function unmergeSelectedNode() {
    const nodeId = state.selectedNodeId;
    if (!nodeId) return;

    // The nodes split back out keep the recipe the merged node was switched to (ticket 043)
    const merges = { ...state.merges };
    const recipes = { ...state.recipes };
    for (const id in merges) {
        if (merges[id] !== nodeId) continue;
        delete merges[id];
        if (state.recipes[nodeId]) recipes[id] = state.recipes[nodeId];
    }

    try {
        render(await requestPlan({ merges, recipes }));
        state.merges = merges;
        state.recipes = recipes;
        save();
        hideNodeDetails();
    } catch (e) {
        console.error("Unmerge failed", e);
        alert(`Unmerge failed: ${e.message}`);
    }
}

/** Records how many of a node's buildings are built (ticket 037); 0 removes the mark. Needs no server. */
export function setBuilt(nodeId, count) {
    const data = getNodeData(nodeId);
    if (!data) return;
    const built = { ...state.built };
    if (count > 0) built[nodeId] = { count, recipe: data.recipe_name }; else delete built[nodeId];
    state.built = built;
    refreshBuilt();
    save();
    renderBuilt(data);
}

/** Uses a node's by-products as supply, sends them to the Sink, or solves the loop they'd close. */
const recipesUsing = new Map();  // item -> the recipes that take it (ticket 059), as the server said

/** Shows a maker's by-product (all of them without `item`), with what can be made from it. */
export async function selectByproduct(makerId, item = null) {
    let recipes = [];
    if (item) {
        try {
            if (!recipesUsing.has(item)) recipesUsing.set(item, await api.fetchRecipesUsing(item));
            recipes = recipesUsing.get(item);
        } catch (e) {
            console.error("Failed to load the recipes using " + item, e);
        }
    }
    showByproductDetails(getNodeData(makerId), item, recipes);
}

/**
 * Sets what the maker does with its by-product `item` (with all of them without it; ticket 059): a choice,
 * Make from it ({choice: 'make', recipe, to}), or null for none of its own.
 */
export async function setByproductChoice(makerId, choice, item = null) {
    const key = item ? `${makerId}|${item}` : makerId;
    const byproducts = { ...state.byproducts, [key]: choice };
    if (choice === null) delete byproducts[key];
    try {
        render(await requestPlan({ byproducts }));
        save();
        if (getNodeData(makerId)) await selectByproduct(makerId, item);
        else hideByproductDetails();
    } catch (e) {
        console.error("By-product change failed", e);
        alert(`By-product change failed: ${e.message}`);
    }
}

// --- Move Branch to Inbound (ticket 045) ---

/** [{item, rate}] with `rate` more of `item` (a new entry if it has none). */
function withMore(entries, item, rate) {
    const found = entries.some(e => e.item === item);
    return found ? entries.map(e => e.item === item ? { ...e, rate: e.rate + rate } : e) : [...entries, { item, rate }];
}

/**
 * The selected node's item becomes inbound production of this plan, so the node and its inputs go. The
 * destination (a tab id, NEW_TAB, or '' for none yet) gets the demand target, linked on the Chain tab.
 */
export async function moveBranch(destination) {
    const data = getNodeData(state.selectedNodeId);
    if (!data) return;
    const item = data.output_item;
    const rate = branchRate(data);
    const before = getDemands();
    setDemands(before.items, before.rates, withMore(before.inbound, item, rate));
    try {
        render(await requestPlan());
        save();
    } catch (e) {
        setDemands(before.items, before.rates, before.inbound);
        console.error("Move failed", e);
        alert(`Move failed: ${e.message}`);
        return;
    }
    hideNodeDetails();

    let where = '';
    if (destination) {
        const source = tabs.activeTab();
        let tab;
        if (destination === NEW_TAB) {
            tab = tabs.addTab({ ...emptyPlan(), items: [item], rates: [rate] }, tabs.uniqueName(item));
        } else {
            tab = tabs.getBook().tabs.find(t => t.id === destination);
            const plan = tab.plan || emptyPlan();
            const demands = withMore((plan.items || []).map((it, i) => ({ item: it, rate: parseFloat(plan.rates[i]) })), item, rate);
            tab.plan = { ...plan, items: demands.map(d => d.item), rates: demands.map(d => d.rate) };
            tabs.saveBook();
        }
        const why = addLink({ tab: tab.id, item }, { tab: source.id, item });
        refreshChain();
        where = ` to ${tab.name}` + (why ? `. Not linked on the Chain tab: ${why}` : '');
    }
    showToast(`Moved ${rate.toFixed(2)}/min ${item}${where}.`, 6000);
}
