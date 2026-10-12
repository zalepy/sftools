// Entry point: plan actions and UI wiring.
import * as api from './api.js';
import {
    state, snapshot, applySaved, savePlan, loadSavedPlan, downloadPlan, readPlanFile,
    loadSavedColors, saveColors, dropIgnoredEntries
} from './state.js';
import {
    renderGraph, refreshNodeColors, hasNodes, fitView, resizeGraph, getNodeData, onNodeSelected, reselectNode, onMergeDrop
} from './graph.js';
import * as panel from './panel.js';

const $ = id => document.getElementById(id);

function currentPlan() {
    return snapshot(panel.getDemands());
}

function save() {
    savePlan(currentPlan());
}

/**
 * Sends the plan (with optional candidate merges/recipes/splits/clocks) and returns the graph nodes.
 * Entries the server ignored are dropped from the candidate objects; callers keep them on success.
 */
async function requestPlan({
    merges = state.merges, recipes = state.recipes, splits = state.splits, clocks = state.clocks
} = {}) {
    const { items, rates } = panel.getDemands();
    const { nodes, ignored } = await api.calculate({
        demands: items.map((item, i) => ({ item, rate: rates[i] })),
        recipes,
        merges,
        splits,
        clocks
    });
    if (ignored.length) {
        dropIgnoredEntries(ignored, { merges, recipes, splits, clocks });
        // Entries on inputs a recipe no longer uses go quietly: that is what the switch (or merge) asked for
        const stale = ignored.filter(entry => !entry.dropped);
        if (stale.length) panel.showPlanNotice(stale);
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
    applySaved(saved);
    recalculate();
}

// --- Node actions ---

async function setClocks(groups) {
    const nodeId = state.selectedNodeId;
    if (!nodeId) return;
    const clocks = { ...state.clocks };
    if (groups) clocks[nodeId] = groups; else delete clocks[nodeId];
    try {
        renderGraph(await requestPlan({ clocks }));
        state.clocks = clocks;
        save();
        reselectNode(nodeId);
    } catch (e) {
        console.error("Clock change failed", e);
        alert(`Clock change failed: ${e.message}`);
    }
}

function applyClocks() {
    setClocks(panel.getClockInputs());
}

function clearClocks() {
    panel.clearClockInputs();
    setClocks(null);
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

    // The merged node runs on the target's clocks
    const clocks = { ...state.clocks };
    delete clocks[sourceId];

    // Allowed, but worth a heads-up: the merged node runs the target's recipe
    const source = getNodeData(sourceId);
    const target = getNodeData(targetId);
    const recipesDiffer = source && target && source.recipe_name !== target.recipe_name;

    try {
        renderGraph(await requestPlan({ merges, clocks }));
        state.merges = merges;
        state.clocks = clocks;
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

/**
 * Splits the selected node into `count` equal parts, or changes the number of parts of the split it
 * belongs to. Parts are '<id>~2', '<id>~3', ... (part 1 keeps the ID); see split_parts on the server.
 */
async function splitSelectedNode(count) {
    const data = getNodeData(state.selectedNodeId);
    if (!data || !(count >= 2)) return;
    const nodeId = data.split ? data.split.of : data.id;
    await changeSplit(nodeId, count, data.id);
}

async function unsplitSelectedNode() {
    const data = getNodeData(state.selectedNodeId);
    if (!data || !data.split) return;
    await changeSplit(data.split.of, 1, data.split.of);
}

// Entries for an ID or anything derived from it: its inputs ('__') and its own parts ('~')
function isUnder(id, nodeId) {
    return id === nodeId || id.startsWith(nodeId + '__') || id.startsWith(nodeId + '~');
}

async function changeSplit(nodeId, count, selectAfter) {
    const oldCount = state.splits[nodeId] || 1;
    const removed = [];
    for (let part = count + 1; part <= oldCount; part++) removed.push(`${nodeId}~${part}`);
    const keep = id => !removed.some(partId => isUnder(id, partId));
    const filter = entries => Object.fromEntries(Object.entries(entries).filter(([id]) => keep(id)));

    const splits = filter(state.splits);
    if (count >= 2) splits[nodeId] = count; else delete splits[nodeId];
    const clocks = filter(state.clocks);
    const recipes = filter(state.recipes);
    const merges = Object.fromEntries(Object.entries(state.merges).filter(([id, target]) => keep(id) && keep(target)));

    try {
        renderGraph(await requestPlan({ splits, clocks, recipes, merges }));
        Object.assign(state, { splits, clocks, recipes, merges });
        save();
        if (getNodeData(selectAfter)) reselectNode(selectAfter); else panel.hideNodeDetails();
    } catch (e) {
        console.error("Split failed", e);
        alert(`Split failed: ${e.message}`);
    }
}

// --- Plan-wide actions ---

function clearAllClocks() {
    if (confirm("Clear all clock speeds? Every node goes back to 100%.")) {
        state.clocks = {};
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
$('clear-clocks-btn').addEventListener('click', clearAllClocks);
$('clear-merges-btn').addEventListener('click', clearMerges);

$('apply-clocks-btn').addEventListener('click', applyClocks);
$('clear-clocks-node-btn').addEventListener('click', clearClocks);
['clock-all', 'clock-last'].forEach(id => $(id).addEventListener('keydown', e => {
    if (e.key === 'Enter') applyClocks();
}));
$('unmerge-btn').addEventListener('click', unmergeSelectedNode);
$('split-btn').addEventListener('click', () => splitSelectedNode(panel.getSplitCount()));
$('unsplit-btn').addEventListener('click', unsplitSelectedNode);
$('recipe-select').addEventListener('change', e => switchRecipe(e.target.value));
$('save-colors-btn').addEventListener('click', saveColorChanges);
$('fit-view-btn').addEventListener('click', fitView);

onNodeSelected(panel.showNodeDetails);
panel.initPanelToggle(resizeGraph);
onMergeDrop(mergeNodes);

// Module scripts run after the document is parsed. Colors first, so the first render uses them.
await loadColors();
loadPlan(loadSavedPlan());
