// The plan shown: asking the server for it, drawing it, saving it (an undo step), and plan-wide actions.
import * as api from '../api.js';
import { state, snapshot, applySaved, dropIgnoredEntries, wrongMode, PLAN_MODE } from '../state.js';
import { renderGraph, refreshBuilt, getNodeData, reselectNode } from '../graph.js';
import * as notes from '../notes.js';
import * as history from '../history.js';
import * as tabs from '../tabs.js';
import { refreshChain } from '../chain.js';
import * as logisticsView from '../logistics.js';
import { $, nodeLabel } from '../panel/common.js';
import { getDemands, setDemands, showLogisticsSettings } from '../panel/planner.js';
import { hideNodeDetails, renderBuilt } from '../panel/node.js';
import { hideByproductDetails, hideEdgeDetails, hideLogisticsDetails } from '../panel/selection.js';
import { refreshLimitControl, showSupply } from '../panel/supply.js';
import { showToast, showPlanNotice, hidePlanNotice } from '../panel/messages.js';

export function currentPlan() {
    return snapshot(getDemands());
}

export function emptyPlan() {
    return { mode: PLAN_MODE, items: [], rates: [], inbound: [] };
}

/** Saves the plan in the browser (in its tab) and records it as an undo step (if it changed). */
export function save() {
    dropGoneNotes();
    const plan = currentPlan();
    tabs.saveActive(plan);
    history.record(plan);
    updateHistoryButtons();
    refreshChain();
}

export function updateHistoryButtons() {
    $('undo-btn').disabled = !history.canUndo();
    $('redo-btn').disabled = !history.canRedo();
}

/** A node's note goes with the node: notes of nodes no longer in the plan are dropped (undo brings them back). */
function dropGoneNotes() {
    const gone = Object.keys(state.notes).filter(id => !getNodeData(id));
    if (!gone.length) return;
    const kept = { ...state.notes };
    gone.forEach(id => delete kept[id]);
    state.notes = kept;
}

/** Hides whatever the Node tab shows. */
export function hideSelection() {
    hideNodeDetails();
    hideByproductDetails();
    hideEdgeDetails();
    hideLogisticsDetails();
}

/** Shows a plan (from the history, or a tab's): the server recalculates it like any other. */
export async function showPlan(plan, failure = 'Undo/redo failed') {
    const selected = state.selectedNodeId;
    setDemands(plan.items, plan.rates, plan.inbound);
    applySaved(plan);
    notes.showPlanNote();
    showLogisticsSettings();
    try {
        render(plan.items && plan.items.length ? await requestPlan() : []);
        save();
        if (selected && getNodeData(selected)) reselectNode(selected); else hideNodeDetails();
    } catch (e) {
        console.error(failure, e);
        alert(`${failure}: ${e.message}`);
    }
}

/** Shows an undo or redo step (null: there's none). */
export async function showHistoryStep(plan) {
    if (plan) await showPlan(plan);
}

/**
 * Sends the plan (with optional candidate merges/recipes/clocks/byproducts) and returns the graph
 * nodes. Entries the server ignored are dropped from the candidate objects; callers keep them on success.
 * By-product choices are the server's (see resolved_byproduct_choices): Calculate passes
 * byproductsDefault 'use', so by-products are used unless set otherwise; other changes leave new ones
 * going to the Sink (ticket 031).
 */
export async function requestPlan({
    merges = state.merges, recipes = state.recipes, clocks = state.clocks,
    byproducts = state.byproducts, byproductsDefault = 'sink', layouts = state.logistics.layouts,
    edges = state.logistics.edges
} = {}) {
    const { items, rates, inbound } = getDemands();
    const { nodes, ignored, byproducts: resolved, logisticsResets, supply, made } = await api.calculate({
        demands: items.map((item, i) => ({ item, rate: rates[i] })),
        inbound,
        recipes,
        merges,
        clocks,
        byproducts,
        byproducts_default: byproductsDefault,
        preferred: state.preferred,
        logistics: { settings: state.logistics.settings, layouts, edges },
        supply_limit: state.supplyLimit
    });
    state.byproducts = resolved;
    state.made = made;
    showSupply(supply);
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
            return `${nodeLabel(nodeId)} (${side === 'out' ? 'output' : 'input'})`;
        });
        showToast(`Logistics reset to the suggested layout: ${names.join(', ')}. Undo to get yours back.`, 6000);
    }
    if (ignored.length) {
        dropIgnoredEntries(ignored, { merges, recipes, clocks });
        // Entries on inputs a recipe no longer uses go quietly: that is what the switch (or merge) asked for
        const stale = ignored.filter(entry => !entry.dropped);
        if (stale.length) showPlanNotice(stale);
    }
    return nodes;
}

/** Draws the graph, and the zoomed-in logistics view if it's open. */
export function render(nodes) {
    renderGraph(nodes);
    refreshLimitControl();
    if (logisticsView.isOpen()) {
        const view = logisticsView.current();
        logisticsView.refreshView(nodes.find(n => n.id === view.nodeId));
    }
}

export async function recalculate(options = {}) {
    if (getDemands().items.length === 0) return;
    try {
        render(await requestPlan(options));
        save();
    } catch (e) {
        console.error("Calculation failed", e);
        alert(`Calculation failed: ${e.message}`);
    }
}

export function loadPlan(saved) {
    if (!saved) return;
    const wrong = wrongMode(saved);
    if (wrong) {
        alert(wrong);
        return;
    }
    setDemands(saved.items, saved.rates, saved.inbound);
    applySaved(saved);
    notes.showPlanNote();
    showLogisticsSettings();
    recalculate();
}

// --- Plan-wide actions ---

export function clearAllClocks() {
    if (confirm("Clear all clock speeds? Every node goes back to 100%.")) {
        state.clocks = {};
        save();
        recalculate();
    }
}

export function clearMerges() {
    if (confirm("Clear all node merges? This will restore the default tree structure.")) {
        state.merges = {};
        save();
        recalculate();
    }
}

/** Starts a fresh plan: no demands, inbound production or adjustments. Logistics settings stay; undo brings it back. */
export function newPlan() {
    if (!confirm("Start a new plan? This clears the demands, inbound production, every adjustment and the notes. Undo brings the plan back.")) return;
    if (logisticsView.isOpen()) logisticsView.closeView();
    notes.discardNodeNote();
    setDemands();
    applySaved({ logistics: { settings: state.logistics.settings } });
    notes.showPlanNote();
    hideSelection();
    hidePlanNotice();
    renderGraph([]);
    refreshLimitControl();
    save();
}

export function clearBuilt() {
    if (confirm("Clear all built marks? Every node counts as not built.")) {
        state.built = {};
        refreshBuilt();
        save();
        const data = getNodeData(state.selectedNodeId);
        if (data) renderBuilt(data);
    }
}
