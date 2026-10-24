// Entry point: wires the page's controls to the actions (actions/), then loads the plan.
import * as api from './api.js';
import { state, downloadPlan, downloadBook, loadPreferred } from './state.js';
import {
    hasNodes, fitView, resizeGraph, getNodeData, refreshNodeColors, onNodeSelected, onMergeDrop,
    onByproductSelected, onLogisticsSelected, onEdgeSelected
} from './graph.js';
import * as notes from './notes.js';
import * as guide from './guide.js';
import * as layouts from './layouts.js';
import * as history from './history.js';
import * as tabs from './tabs.js';
import { $ } from './panel/common.js';
import { showTab, initPanelToggle, initLegendToggle } from './panel/shell.js';
import { addRow, addInboundRow } from './panel/planner.js';
import { showNodeDetails, hideNodeDetails, getBuiltCount } from './panel/node.js';
import { openMoveBranch, closeMoveBranch, moveBranchDestination } from './panel/move-branch.js';
import {
    showLogisticsDetails, hideLogisticsDetails, showEdgeDetails, hideEdgeDetails, showByproductDetails, hideByproductDetails
} from './panel/selection.js';
import { initRecipeList } from './panel/recipes.js';
import { initColorDefine } from './panel/colors.js';
import {
    currentPlan, showHistoryStep, recalculate, loadPlan, clearAllClocks, clearMerges, newPlan, clearBuilt
} from './actions/plan.js';
import { leaveNotes, keepSelection, saveNodeNote, savePlanNote } from './actions/notes.js';
import { switchTab, showChain, addTab, duplicateTab, closeTab, importFile } from './actions/tabs.js';
import {
    applyClocks, fitClock, clearClocks, switchRecipe, mergeNodes, unmergeSelectedNode, setBuilt, setByproductChoice, moveBranch,
    selectByproduct
} from './actions/node.js';
import { changeLogisticsSettings, zoomIn, setEdgeBelts } from './actions/logistics.js';
import { setPreferred, changePreferred, preferSelected, loadColors, saveColorChanges } from './actions/preferences.js';
import { setSupplyLimit, rowsChanged } from './actions/supply.js';

const undo = () => leaveNotes() && showHistoryStep(history.undo());
const redo = () => leaveNotes() && showHistoryStep(history.redo());

// --- Side panel tabs ---

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const tabId = tab.dataset.tab;
        showTab(tabId);

        // Colors may have changed on the colors tab
        if (tabId !== 'colors' && hasNodes()) {
            refreshNodeColors();
        }
    });
});

// --- Planner tab ---

// Calculate uses by-products as supply unless set otherwise; nothing else does (ticket 031). Not before
// startup has loaded the tabs (below): the plan would have no tab to be saved in.
let started = false;
$('demand-form').addEventListener('submit', e => {
    e.preventDefault();
    if (started) recalculate({ byproductsDefault: 'use' });
});
$('add-row-btn').addEventListener('click', addRow);
$('add-inbound-btn').addEventListener('click', addInboundRow);
['demand-rows', 'inbound-rows'].forEach(id => ['input', 'click'].forEach(type => $(id).addEventListener(type, rowsChanged)));
$('supply-limit').addEventListener('change', e => setSupplyLimit(e.target.checked));
$('new-plan-btn').addEventListener('click', newPlan);
$('export-btn').addEventListener('click', () => downloadPlan(currentPlan(), tabs.activeTab().name));
$('save-book-btn').addEventListener('click', () => downloadBook(tabs.getBook()));
$('import-btn').addEventListener('click', () => $('import-input').click());
$('import-input').addEventListener('change', e => importFile(e.target));
$('clear-clocks-btn').addEventListener('click', clearAllClocks);
$('clear-merges-btn').addEventListener('click', clearMerges);
$('clear-built-btn').addEventListener('click', clearBuilt);
['belt-tier', 'pipe-tier', 'smart-splitters'].forEach(id => $(id).addEventListener('change', changeLogisticsSettings));
$('save-plan-note-btn').addEventListener('click', savePlanNote);

// --- Node tab ---

$('built-count').addEventListener('change', () => setBuilt(state.selectedNodeId, getBuiltCount()));
$('built-all-btn').addEventListener('click', e => setBuilt(state.selectedNodeId, parseInt(e.target.dataset.count, 10)));
$('apply-clocks-btn').addEventListener('click', applyClocks);
$('clear-clocks-node-btn').addEventListener('click', clearClocks);
$('fit-clock-btn').addEventListener('click', fitClock);
['clock-all', 'clock-last'].forEach(id => $(id).addEventListener('keydown', e => {
    if (e.key === 'Enter') applyClocks();
}));
$('unmerge-btn').addEventListener('click', unmergeSelectedNode);
$('move-branch-btn').addEventListener('click', () => openMoveBranch(tabs.getBook().tabs, tabs.getBook().active));
$('move-branch-cancel').addEventListener('click', closeMoveBranch);
$('move-branch-confirm').addEventListener('click', () => moveBranch(moveBranchDestination()));
$('save-node-note-btn').addEventListener('click', saveNodeNote);
$('recipe-select').addEventListener('change', e => switchRecipe(e.target.value));
$('prefer-btn').addEventListener('click', () => preferSelected(true));
$('unprefer-btn').addEventListener('click', () => preferSelected(false));
['byproduct-toggle-btn', 'byproduct-sink-btn', 'byproduct-solve-btn'].forEach(id => $(id).addEventListener('click', e => {
    const { maker, choice, item } = e.target.dataset;
    setByproductChoice(maker, choice, item || null);
}));
['byproduct-make', 'byproduct-make-to'].forEach(id => $(id).addEventListener('change', () => {
    const { maker, item } = $('byproduct-make').dataset;
    const recipe = $('byproduct-make').value;
    setByproductChoice(maker, recipe ? { choice: 'make', recipe, to: $('byproduct-make-to').value } : null, item);
}));
$('logistics-zoom-btn').addEventListener('click', e => zoomIn(e.target.dataset.node, e.target.dataset.side));
$('edge-belt-more').addEventListener('click', e => setEdgeBelts(e.target.dataset.key, parseInt(e.target.dataset.count, 10) + 1));
$('edge-belt-fewer').addEventListener('click', e => setEdgeBelts(e.target.dataset.key, parseInt(e.target.dataset.count, 10) - 1));
$('edge-belt-default').addEventListener('click', e => setEdgeBelts(e.target.dataset.key, null));

// --- Colors tab ---

$('save-colors-btn').addEventListener('click', saveColorChanges);
initColorDefine();

// --- Undo and redo ---

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

// --- Graph: selecting shows it on the Node tab, unless the user keeps an unsaved note ---

onNodeSelected(data => {
    if (data.id !== state.selectedNodeId && !leaveNotes({ plan: false })) return keepSelection();
    hideByproductDetails();
    hideEdgeDetails();
    hideLogisticsDetails();
    showNodeDetails(data);
    showTab('node');
});
onByproductSelected((makerId, item) => {
    if (!leaveNotes({ plan: false })) return keepSelection();
    hideNodeDetails();
    hideLogisticsDetails();
    showByproductDetails(getNodeData(makerId), item);
    selectByproduct(makerId, item);  // again with what can be made from it, once the server says
    showTab('node');
});
onLogisticsSelected((nodeId, side) => {
    if (!leaveNotes({ plan: false })) return keepSelection();
    hideNodeDetails();
    hideByproductDetails();
    hideEdgeDetails();
    showLogisticsDetails(getNodeData(nodeId), side);
    showTab('node');
});
onEdgeSelected(edge => {
    if (!leaveNotes({ plan: false })) return keepSelection();
    hideNodeDetails();
    hideLogisticsDetails();
    if (!edge.byproduct) hideByproductDetails();
    showEdgeDetails(edge);
    showTab('node');
});
onMergeDrop(mergeNodes);
$('fit-view-btn').addEventListener('click', fitView);

// --- Header ---

initPanelToggle(resizeGraph);
// The legend, the guide and the layouts share a place: opening one closes the others
const legend = initLegendToggle({ opened: () => { guide.closeGuide(); layouts.closeLayouts(); } });
guide.initGuide({ opened: () => { legend.hide(); layouts.closeLayouts(); } });
layouts.initLayouts({ opened: () => { legend.hide(); guide.closeGuide(); } });
notes.initNoteBox();

// --- Startup ---

// Module scripts run after the document is parsed. Colors first, so the first render uses them.
await loadColors();
loadPreferred();
// Both requests at once, so startup waits for one round trip
const recipeChoicesRequest = api.fetchRecipeChoices();
const powerRequest = api.fetchPowerItems();
let recipeChoices = [];
try {
    recipeChoices = await recipeChoicesRequest;
} catch (e) {
    console.error("Failed to load recipe choices", e);
}
initRecipeList(recipeChoices, setPreferred);
try {
    state.power = await powerRequest;
} catch (e) {
    console.error("Failed to load the fuels", e);
}
$('recipe-reset-all').addEventListener('click', () => {
    if (Object.keys(state.preferred).length && confirm('Every item back to its default recipe, in every tab?')) changePreferred({});
});
tabs.loadBook();
tabs.initTabs({ onSwitch: switchTab, onClose: closeTab, onAdd: addTab, onDuplicate: duplicateTab, onChain: showChain });
history.useTab(tabs.activeTab().id);
loadPlan(tabs.activeTab().plan);
started = true;
$('calculate-btn').disabled = false;
$('calculate-btn').title = '';
