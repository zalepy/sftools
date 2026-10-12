// Entry point: plan actions and UI wiring.
import * as api from './api.js';
import {
    state, snapshot, applySaved, savePlan, loadSavedPlan, downloadPlan, readPlanFile,
    loadSavedColors, saveColors, dropIgnoredEntries
} from './state.js';
import { renderGraph, refreshNodeColors, hasNodes, fitView, getNodeData, onNodeSelected, reselectNode, onMergeDrop } from './graph.js';
import * as panel from './panel.js';

const $ = id => document.getElementById(id);

function currentPlan() {
    return snapshot(panel.getDemands(), panel.getRoundUp());
}

function save() {
    savePlan(currentPlan());
}

/**
 * Sends the plan (with optional candidate merges/overrides/recipes) and returns the graph nodes.
 * Entries the server ignored are dropped from the candidate objects; callers keep them on success.
 */
async function requestPlan({ merges = state.merges, overrides = state.overrides, recipes = state.recipes } = {}) {
    const { items, rates } = panel.getDemands();
    const { nodes, ignored } = await api.calculate({
        demands: items.map((item, i) => ({ item, rate: rates[i] })),
        roundUp: panel.getRoundUp(),
        recipes,
        merges,
        overrides
    });
    if (ignored.length) {
        dropIgnoredEntries(ignored, { merges, overrides, recipes });
        panel.showPlanNotice(ignored);
    }
    return nodes;
}

async function recalculate() {
    if (panel.getDemands().items.length === 0) return;
    try {
        renderGraph(await requestPlan());
        save();
    } catch (e) {
        console.error("Calculation failed", e);
        alert(`Calculation failed: ${e.message}`);
    }
}

function loadPlan(saved) {
    if (!saved) return;
    panel.setDemands(saved.items, saved.rates);
    panel.setRoundUp(saved.roundUp ?? true);
    applySaved(saved);
    recalculate();
}

// --- Node actions ---

function applyOverride() {
    const nodeId = state.selectedNodeId;
    if (!nodeId) return;
    const value = panel.getOverrideInput();
    if (!isNaN(value) && value > 0) {
        state.overrides[nodeId] = value;
    } else {
        delete state.overrides[nodeId];
    }
    recalculate();
}

function clearOverride() {
    panel.clearOverrideInput();
    if (state.selectedNodeId) delete state.overrides[state.selectedNodeId];
    recalculate();
}

async function switchRecipe(recipeName) {
    const nodeId = state.selectedNodeId;
    if (!recipeName || !nodeId) return;

    const recipes = { ...state.recipes, [nodeId]: recipeName };
    try {
        renderGraph(await requestPlan({ recipes }));
        state.recipes = recipes;
        save();
        reselectNode(nodeId);
    } catch (e) {
        console.error("Recipe switch failed", e);
        alert(`Recipe switch failed: ${e.message}`);
    }
}

async function mergeNodes(sourceId, targetId) {
    // Flattening: anything merged into the source now points at the target
    const merges = { ...state.merges };
    for (const id in merges) {
        if (merges[id] === sourceId) merges[id] = targetId;
    }
    merges[sourceId] = targetId;

    const overrides = { ...state.overrides };
    delete overrides[sourceId];

    // Allowed, but worth a heads-up: the merged node runs the target's recipe
    const source = getNodeData(sourceId);
    const target = getNodeData(targetId);
    const recipesDiffer = source && target && source.recipe_name !== target.recipe_name;

    try {
        renderGraph(await requestPlan({ merges, overrides }));
        state.merges = merges;
        state.overrides = overrides;
        save();
        if (recipesDiffer) {
            panel.showToast(`Merged nodes with different recipes: ${source.recipe_name} into ${target.recipe_name}. The merged node runs ${target.recipe_name}.`);
        }
    } catch (e) {
        console.error("Merge failed", e);
        alert(`Merge failed: ${e.message}`);
    }
}

async function unmergeSelectedNode() {
    const nodeId = state.selectedNodeId;
    if (!nodeId) return;

    const merges = { ...state.merges };
    for (const id in merges) {
        if (merges[id] === nodeId) delete merges[id];
    }

    try {
        renderGraph(await requestPlan({ merges }));
        state.merges = merges;
        save();
        panel.hideNodeDetails();
    } catch (e) {
        console.error("Unmerge failed", e);
        alert(`Unmerge failed: ${e.message}`);
    }
}

// --- Plan-wide actions ---

function clearOverrides() {
    if (confirm("Clear all manual scale adjustments?")) {
        state.overrides = {};
        save();
        recalculate();
    }
}

function clearMerges() {
    if (confirm("Clear all node merges? This will restore the default tree structure.")) {
        state.merges = {};
        save();
        recalculate();
    }
}

async function importPlan(input) {
    const file = input.files[0];
    if (!file) return;
    try {
        loadPlan(await readPlanFile(file));
        save();
    } catch (err) {
        alert("Failed to parse JSON file.");
        console.error(err);
    }
    input.value = ''; // allow importing the same file again
}

// --- Colors ---

async function loadColors() {
    let defaults = {};
    try {
        defaults = await api.fetchDefaultColors();
    } catch (e) {
        console.error("Failed to load colors", e);
    }
    state.colors = { ...defaults, ...loadSavedColors() };
    panel.renderColorList();
}

function saveColorChanges() {
    try {
        saveColors(panel.readColorInputs());
        alert('Colors saved in this browser.');
    } catch (e) {
        console.error("Failed to save colors", e);
    }
}

// --- Tabs ---

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const tabId = tab.dataset.tab;
        document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
        tab.classList.add('active');
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        $(`${tabId}-tab`).classList.add('active');

        // Colors may have changed on the colors tab
        if (tabId === 'planner' && hasNodes()) {
            refreshNodeColors();
        }
    });
});

// --- Wiring ---

$('demand-form').addEventListener('submit', e => {
    e.preventDefault();
    recalculate();
});
$('add-row-btn').addEventListener('click', panel.addRow);
$('export-btn').addEventListener('click', () => downloadPlan(currentPlan()));
$('import-btn').addEventListener('click', () => $('import-input').click());
$('import-input').addEventListener('change', e => importPlan(e.target));
$('clear-overrides-btn').addEventListener('click', clearOverrides);
$('clear-merges-btn').addEventListener('click', clearMerges);
$('round-up-toggle').addEventListener('change', recalculate);

$('apply-override-btn').addEventListener('click', applyOverride);
$('clear-override-btn').addEventListener('click', clearOverride);
$('override-scale').addEventListener('keydown', e => {
    if (e.key === 'Enter') applyOverride();
});
$('unmerge-btn').addEventListener('click', unmergeSelectedNode);
$('recipe-select').addEventListener('change', e => switchRecipe(e.target.value));
$('save-colors-btn').addEventListener('click', saveColorChanges);
$('fit-view-btn').addEventListener('click', fitView);

onNodeSelected(panel.showNodeDetails);
onMergeDrop(mergeNodes);

// Module scripts run after the document is parsed. Colors first, so the first render uses them.
await loadColors();
loadPlan(loadSavedPlan());
