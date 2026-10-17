// Entry point: plan actions and UI wiring.
import * as api from './api.js';
import {
    state, snapshot, applySaved, downloadPlan, downloadBook, isBook, readPlanFile,
    loadSavedColors, saveColors, dropIgnoredEntries, PLAN_MODE, wrongMode, loadPreferred, savePreferred
} from './state.js';
import {
    renderGraph, refreshNodeColors, refreshBuilt, hasNodes, fitView, resizeGraph, getNodeData, onNodeSelected, reselectNode, onMergeDrop,
    onByproductSelected, onLogisticsSelected, selectLogistics, onEdgeSelected, getEdgeData
} from './graph.js';
import * as panel from './panel.js';
import * as history from './history.js';
import * as tabs from './tabs.js';
import { openChain, refreshChain, closeChain, isChainOpen } from './chain.js';
import * as logisticsView from './logistics.js';

const $ = id => document.getElementById(id);

function currentPlan() {
    return snapshot(panel.getDemands());
}

/** Saves the plan in the browser (in its tab) and records it as an undo step (if it changed). */
function save() {
    const plan = currentPlan();
    tabs.saveActive(plan);
    history.record(plan);
    updateHistoryButtons();
    refreshChain();
}

function updateHistoryButtons() {
    $('undo-btn').disabled = !history.canUndo();
    $('redo-btn').disabled = !history.canRedo();
}

/** Shows a plan (from the history, or a tab's): the server recalculates it like any other. */
async function showPlan(plan, failure = 'Undo/redo failed') {
    const selected = state.selectedNodeId;
    panel.setDemands(plan.items, plan.rates, plan.inbound);
    applySaved(plan);
    showLogisticsSettings();
    try {
        render(plan.items && plan.items.length ? await requestPlan() : []);
        save();
        if (selected && getNodeData(selected)) reselectNode(selected); else panel.hideNodeDetails();
    } catch (e) {
        console.error(failure, e);
        alert(`${failure}: ${e.message}`);
    }
}

async function showHistoryStep(plan) {
    if (plan) await showPlan(plan);
}

const undo = () => showHistoryStep(history.undo());
const redo = () => showHistoryStep(history.redo());

// --- Plan tabs (ticket 039) ---

function emptyPlan() {
    return { mode: PLAN_MODE, items: [], rates: [], inbound: [] };
}

/**
 * Shows another tab, with its own undo history. Logistics settings (what's unlocked) are the game's, so
 * they stay as they are, except for a plan just imported, which brings its own.
 */
async function switchTab(id, { ownSettings = false, reload = false } = {}) {
    if (isChainOpen()) {
        closeChain();
        tabs.setChainShown(false);
    }
    if (id === tabs.getBook().active && !reload) return;
    if (logisticsView.isOpen()) logisticsView.closeView();
    const settings = state.logistics.settings;
    tabs.setActive(id);
    history.useTab(id);
    state.selectedNodeId = null;
    panel.hideNodeDetails();
    panel.hideByproductDetails();
    panel.hideEdgeDetails();
    panel.hideLogisticsDetails();
    panel.hidePlanNotice();
    const plan = tabs.activeTab().plan || emptyPlan();
    await showPlan(ownSettings ? plan : { ...plan, logistics: { ...plan.logistics, settings } }, 'Opening the tab failed');
    updateHistoryButtons();
}

/** Shows the chain tab (ticket 040) over the graph; the side panel keeps the active plan. */
function showChain() {
    if (isChainOpen()) return;
    if (logisticsView.isOpen()) logisticsView.closeView();
    tabs.setChainShown(true);
    openChain(id => switchTab(id));
}

function addTab() {
    switchTab(tabs.addTab(emptyPlan()).id);
}

function duplicateTab() {
    const copy = JSON.parse(JSON.stringify(currentPlan()));
    switchTab(tabs.addTab(copy, `${tabs.activeTab().name} (copy)`).id);
}

async function closeTab(id) {
    const tab = tabs.getBook().tabs.find(t => t.id === id);
    if (!tab) return;
    const planned = tab.plan && tab.plan.items && tab.plan.items.length;
    const links = tabs.getBook().chain.links.filter(l => l.from.tab === id || l.to.tab === id).length;
    const linked = links ? ` Its ${links} link${links === 1 ? '' : 's'} in the chain tab go too.` : '';
    if ((planned || links) && !confirm(`Close "${tab.name}"? Its plan is removed from this browser; Export Plan or Save Book first to keep it.${linked}`)) return;
    if (tabs.getBook().tabs.length === 1) tabs.addTab(emptyPlan());  // there's always a tab
    const chainShown = isChainOpen();
    const next = tabs.removeTab(id);
    history.forget(id);
    if (next) {
        await switchTab(next.id, { reload: true });
        if (chainShown) showChain();
    }
    refreshChain();
}

/** Replaces all the tabs with a saved book's (Save Book, ticket 039). */
async function openBook(data) {
    const list = data.tabs.filter(tab => tab && typeof tab === 'object').map((tab, i) => ({
        id: typeof tab.id === 'string' && tab.id ? tab.id : tabs.newTabId(),
        name: typeof tab.name === 'string' && tab.name.trim() ? tab.name.trim() : `Plan ${i + 1}`,
        plan: tab.plan || null
    }));
    if (!list.length) {
        alert('This book has no plans.');
        return;
    }
    const here = tabs.getBook().tabs.length;
    if (!confirm(`Load this book? Its ${list.length} tab(s) replace the ${here} here; Save Book first to keep them.`)) return;
    history.reset();
    // A book brings its preferred recipes and colors (ticket 043), for this browser's tabs
    const isMap = value => Boolean(value) && typeof value === 'object' && !Array.isArray(value);
    if (isMap(data.preferred)) {
        savePreferred(data.preferred);
        panel.renderRecipeList();
    }
    if (isMap(data.colors)) {
        saveColors({ ...state.colors, ...data.colors });
        panel.renderColorList();
    }
    tabs.replaceBook(list, data.active, data.chain);
    await switchTab(tabs.getBook().active, { ownSettings: true, reload: true });
}

/**
 * Sends the plan (with optional candidate merges/recipes/clocks/byproducts) and returns the graph
 * nodes. Entries the server ignored are dropped from the candidate objects; callers keep them on success.
 * By-product choices are the server's (see resolved_byproduct_choices): Calculate passes
 * byproductsDefault 'use', so by-products are used unless set otherwise; other changes leave new ones
 * going to the Sink (ticket 031).
 */
async function requestPlan({
    merges = state.merges, recipes = state.recipes, clocks = state.clocks,
    byproducts = state.byproducts, byproductsDefault = 'sink', layouts = state.logistics.layouts,
    edges = state.logistics.edges
} = {}) {
    const { items, rates, inbound } = panel.getDemands();
    const { nodes, ignored, byproducts: resolved, logisticsResets } = await api.calculate({
        demands: items.map((item, i) => ({ item, rate: rates[i] })),
        inbound,
        recipes,
        merges,
        clocks,
        byproducts,
        byproducts_default: byproductsDefault,
        preferred: state.preferred,
        logistics: { settings: state.logistics.settings, layouts, edges }
    });
    state.byproducts = resolved;
    // The dashed border shows the clocks of the plan just calculated; callers keep them in state afterwards
    nodes.forEach(node => { node.clocks_set = Boolean(clocks[node.id]); });
    // Edited logistics nodes whose buildings or edges changed go back to the suggested layout
    if (logisticsResets.length) {
        logisticsResets.forEach(reset => {
            delete layouts[reset.key];
            delete state.logistics.positions[reset.key];
        });
        const names = logisticsResets.map(reset => {
            const [nodeId, side] = reset.key.split('|');
            return `${panel.nodeLabel(nodeId)} (${side === 'out' ? 'output' : 'input'})`;
        });
        panel.showToast(`Logistics reset to the suggested layout: ${names.join(', ')}. Undo to get yours back.`, 6000);
    }
    if (ignored.length) {
        dropIgnoredEntries(ignored, { merges, recipes, clocks });
        // Entries on inputs a recipe no longer uses go quietly: that is what the switch (or merge) asked for
        const stale = ignored.filter(entry => !entry.dropped);
        if (stale.length) panel.showPlanNotice(stale);
    }
    return nodes;
}

/** Draws the graph, and the zoomed-in logistics view if it's open. */
function render(nodes) {
    renderGraph(nodes);
    if (logisticsView.isOpen()) {
        const view = logisticsView.current();
        logisticsView.refreshView(nodes.find(n => n.id === view.nodeId));
    }
}

async function recalculate(options = {}) {
    if (panel.getDemands().items.length === 0) return;
    try {
        render(await requestPlan(options));
        save();
    } catch (e) {
        console.error("Calculation failed", e);
        alert(`Calculation failed: ${e.message}`);
    }
}

function loadPlan(saved) {
    if (!saved) return;
    const wrong = wrongMode(saved);
    if (wrong) {
        alert(wrong);
        return;
    }
    panel.setDemands(saved.items, saved.rates, saved.inbound);
    applySaved(saved);
    showLogisticsSettings();
    recalculate();
}

// --- Node actions ---

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
        render(await requestPlan({ recipes }));
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
        render(await requestPlan({ merges, clocks }));
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

/** Records how many of a node's buildings are built (ticket 037); 0 removes the mark. Needs no server. */
function setBuilt(nodeId, count) {
    const data = getNodeData(nodeId);
    if (!data) return;
    const built = { ...state.built };
    if (count > 0) built[nodeId] = { count, recipe: data.recipe_name }; else delete built[nodeId];
    state.built = built;
    refreshBuilt();
    save();
    panel.renderBuilt(data);
}

/** Uses a node's by-products as supply, sends them to the Sink, or solves the loop they'd close. */
async function setByproductChoice(makerId, choice) {
    const byproducts = { ...state.byproducts, [makerId]: choice };
    try {
        render(await requestPlan({ byproducts }));
        save();
        if (getNodeData(makerId)) panel.showByproductDetails(getNodeData(makerId));
        else panel.hideByproductDetails();
    } catch (e) {
        console.error("By-product change failed", e);
        alert(`By-product change failed: ${e.message}`);
    }
}

async function unmergeSelectedNode() {
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
        panel.hideNodeDetails();
    } catch (e) {
        console.error("Unmerge failed", e);
        alert(`Unmerge failed: ${e.message}`);
    }
}

// --- Logistics (ticket 033) ---

function readLogisticsSettings() {
    return {
        belt_tier: parseInt($('belt-tier').value, 10),
        pipe_tier: parseInt($('pipe-tier').value, 10),
        smart: $('smart-splitters').checked
    };
}

function showLogisticsSettings() {
    const settings = state.logistics.settings;
    $('belt-tier').value = String(settings.belt_tier);
    $('pipe-tier').value = String(settings.pipe_tier);
    $('smart-splitters').checked = settings.smart;
}

async function changeLogisticsSettings() {
    state.logistics.settings = readLogisticsSettings();
    await recalculate();
}

/** Applies an edited layout of one side (null: back to the suggested one). */
async function setLayout(nodeId, side, layout) {
    const key = `${nodeId}|${side}`;
    const layouts = { ...state.logistics.layouts };
    if (layout) layouts[key] = layout; else delete layouts[key];
    if (!layout) delete state.logistics.positions[key];  // the suggested layout, drawn as suggested
    try {
        render(await requestPlan({ layouts }));
        state.logistics.layouts = layouts;
        save();
        selectLogistics(nodeId, side);
    } catch (e) {
        console.error("Logistics change failed", e);
        alert(`Logistics change failed: ${e.message}`);
    }
}

function zoomIn(nodeId, side, select = null) {
    const node = getNodeData(nodeId);
    if (!node || !node.logistics || !node.logistics[side]) {
        panel.showToast("That end isn't in the plan's logistics: it's the demand, the Sink or inbound production.");
        return;
    }
    logisticsView.openView(node, side, {
        onChange: layout => setLayout(nodeId, side, layout),
        describe: panel.nodeLabel,
        onMove: save,
        onBelts: setEdgeBelts,
        onOpen: zoomIn
    }, select);
}

/**
 * Sets how many belts an edge has (ticket 041); null goes back to the fewest its rate needs. The layouts
 * of both its ends are suggested again (the server resets edited ones, with a notice).
 */
async function setEdgeBelts(key, count) {
    const edges = { ...state.logistics.edges };
    if (count === null) delete edges[key]; else edges[key] = count;
    try {
        render(await requestPlan({ edges }));
        state.logistics.edges = edges;
        save();
        const edge = getEdgeData(key);
        if (edge) panel.showEdgeDetails(edge); else panel.hideEdgeDetails();
    } catch (e) {
        console.error("Belt change failed", e);
        alert(`Belt change failed: ${e.message}`);
    }
}

function wireLogistics() {
    onLogisticsSelected((nodeId, side) => {
        panel.hideNodeDetails();
        panel.hideByproductDetails();
        panel.hideEdgeDetails();
        panel.showLogisticsDetails(getNodeData(nodeId), side);
        panel.showTab('node');
    });
    $('logistics-zoom-btn').addEventListener('click', e => zoomIn(e.target.dataset.node, e.target.dataset.side));
    onEdgeSelected(edge => {
        panel.hideNodeDetails();
        panel.hideLogisticsDetails();
        if (!edge.byproduct) panel.hideByproductDetails();
        panel.showEdgeDetails(edge);
        panel.showTab('node');
    });
    $('edge-belt-more').addEventListener('click', e => setEdgeBelts(e.target.dataset.key, parseInt(e.target.dataset.count, 10) + 1));
    $('edge-belt-fewer').addEventListener('click', e => setEdgeBelts(e.target.dataset.key, parseInt(e.target.dataset.count, 10) - 1));
    $('edge-belt-default').addEventListener('click', e => setEdgeBelts(e.target.dataset.key, null));
    ['belt-tier', 'pipe-tier', 'smart-splitters'].forEach(id => $(id).addEventListener('change', changeLogisticsSettings));
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

/** Starts a fresh plan: no demands, inbound production or adjustments. Logistics settings stay; undo brings it back. */
function newPlan() {
    if (!confirm("Start a new plan? This clears the demands, inbound production and every adjustment. Undo brings the plan back.")) return;
    if (logisticsView.isOpen()) logisticsView.closeView();
    panel.setDemands();
    applySaved({ logistics: { settings: state.logistics.settings } });
    panel.hideNodeDetails();
    panel.hideByproductDetails();
    panel.hideEdgeDetails();
    panel.hideLogisticsDetails();
    panel.hidePlanNotice();
    renderGraph([]);
    save();
}

function clearBuilt() {
    if (confirm("Clear all built marks? Every node counts as not built.")) {
        state.built = {};
        refreshBuilt();
        save();
        const data = getNodeData(state.selectedNodeId);
        if (data) panel.renderBuilt(data);
    }
}

/** Opens a plan file in a new tab, or a book file in place of all the tabs. */
async function importFile(input) {
    const file = input.files[0];
    if (!file) return;
    input.value = ''; // allow importing the same file again
    let data;
    try {
        data = await readPlanFile(file);
    } catch (err) {
        alert("Failed to parse JSON file.");
        console.error(err);
        return;
    }
    const wrong = data && wrongMode(data);
    if (wrong) {
        alert(wrong);
        return;
    }
    if (isBook(data)) {
        await openBook(data);
        return;
    }
    const name = typeof data.name === 'string' && data.name.trim() ? data.name.trim() : file.name.replace(/\.json$/i, '');
    await switchTab(tabs.addTab(data, name).id, { ownSettings: true });
}

// --- Preferred recipes (ticket 043) ---

/** Prefers a recipe for an item (null, or its default: back to the default), in every tab. */
function setPreferred(item, recipe) {
    const preferred = { ...state.preferred };
    if (recipe && recipe !== panel.defaultRecipe(item)) preferred[item] = recipe; else delete preferred[item];
    return changePreferred(preferred, item, preferred[item]);
}

/** Replaces the preferred recipes; recalculates the plan shown. `item`/`recipe`: the one just preferred. */
async function changePreferred(preferred, item = null, recipe = null) {
    const previous = state.preferred;
    // A node's own choice of the same recipe goes: it follows the preferred one from now on
    const recipes = Object.fromEntries(Object.entries(state.recipes)
        .filter(([id, name]) => !(recipe && name === recipe && getNodeData(id)?.output_item === item)));
    savePreferred(preferred);
    panel.renderRecipeList();
    if (!hasNodes()) return;
    try {
        render(await requestPlan({ recipes }));
        state.recipes = recipes;
        save();
        if (state.selectedNodeId) reselectNode(state.selectedNodeId);
        const own = item ? panel.ownRecipeNodes(item).length : 0;
        if (own) panel.showToast(`${own} ${item} node${own === 1 ? '' : 's'} here keep${own === 1 ? 's' : ''} a recipe of ${own === 1 ? 'its' : 'their'} own.`);
    } catch (e) {
        savePreferred(previous);
        panel.renderRecipeList();
        console.error("Preferred recipe change failed", e);
        alert(`Preferred recipe change failed: ${e.message}`);
    }
}

function preferSelected(prefer) {
    const data = getNodeData(state.selectedNodeId);
    if (data) setPreferred(data.output_item, prefer ? data.recipe_name : null);
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
        panel.showTab(tabId);

        // Colors may have changed on the colors tab
        if (tabId !== 'colors' && hasNodes()) {
            refreshNodeColors();
        }
    });
});

// --- Wiring ---

// Calculate uses by-products as supply unless set otherwise; nothing else does (ticket 031)
$('demand-form').addEventListener('submit', e => {
    e.preventDefault();
    recalculate({ byproductsDefault: 'use' });
});
$('add-row-btn').addEventListener('click', panel.addRow);
$('add-inbound-btn').addEventListener('click', panel.addInboundRow);
$('new-plan-btn').addEventListener('click', newPlan);
$('export-btn').addEventListener('click', () => downloadPlan(currentPlan(), tabs.activeTab().name));
$('save-book-btn').addEventListener('click', () => downloadBook(tabs.getBook()));
$('import-btn').addEventListener('click', () => $('import-input').click());
$('import-input').addEventListener('change', e => importFile(e.target));
$('clear-clocks-btn').addEventListener('click', clearAllClocks);
$('clear-merges-btn').addEventListener('click', clearMerges);
$('clear-built-btn').addEventListener('click', clearBuilt);
$('built-count').addEventListener('change', () => setBuilt(state.selectedNodeId, panel.getBuiltCount()));
$('built-all-btn').addEventListener('click', e => setBuilt(state.selectedNodeId, parseInt(e.target.dataset.count, 10)));

$('apply-clocks-btn').addEventListener('click', applyClocks);
$('clear-clocks-node-btn').addEventListener('click', clearClocks);
['clock-all', 'clock-last'].forEach(id => $(id).addEventListener('keydown', e => {
    if (e.key === 'Enter') applyClocks();
}));
$('unmerge-btn').addEventListener('click', unmergeSelectedNode);
$('undo-btn').addEventListener('click', undo);
$('redo-btn').addEventListener('click', redo);

// Ctrl+Z / Ctrl+Y (or Ctrl+Shift+Z), except while typing, where they edit the text
document.addEventListener('keydown', e => {
    if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
    if (e.target.closest('input, textarea, select, [contenteditable]')) return;
    const key = e.key.toLowerCase();
    if (key === 'z' && !e.shiftKey) {
        e.preventDefault();
        undo();
    } else if (key === 'y' || (key === 'z' && e.shiftKey)) {
        e.preventDefault();
        redo();
    }
});
$('recipe-select').addEventListener('change', e => switchRecipe(e.target.value));
$('prefer-btn').addEventListener('click', () => preferSelected(true));
$('unprefer-btn').addEventListener('click', () => preferSelected(false));
$('save-colors-btn').addEventListener('click', saveColorChanges);
$('fit-view-btn').addEventListener('click', fitView);

onNodeSelected(data => {
    panel.hideByproductDetails();
    panel.hideEdgeDetails();
    panel.hideLogisticsDetails();
    panel.showNodeDetails(data);
    panel.showTab('node');
});
onByproductSelected(makerId => {
    panel.hideNodeDetails();
    panel.hideLogisticsDetails();
    panel.showByproductDetails(getNodeData(makerId));
    panel.showTab('node');
});
wireLogistics();
['byproduct-toggle-btn', 'byproduct-solve-btn'].forEach(id => $(id).addEventListener('click', e => {
    const { maker, choice } = e.target.dataset;
    setByproductChoice(maker, choice);
}));
panel.initPanelToggle(resizeGraph);
panel.initLegendToggle();
onMergeDrop(mergeNodes);

// Module scripts run after the document is parsed. Colors first, so the first render uses them.
await loadColors();
loadPreferred();
let recipeChoices = [];
try {
    recipeChoices = await api.fetchRecipeChoices();
} catch (e) {
    console.error("Failed to load recipe choices", e);
}
panel.initRecipeList(recipeChoices, setPreferred);
$('recipe-reset-all').addEventListener('click', () => {
    if (Object.keys(state.preferred).length && confirm('Every item back to its default recipe, in every tab?')) changePreferred({});
});
tabs.loadBook();
tabs.initTabs({ onSwitch: switchTab, onClose: closeTab, onAdd: addTab, onDuplicate: duplicateTab, onChain: showChain });
history.useTab(tabs.activeTab().id);
loadPlan(tabs.activeTab().plan);
