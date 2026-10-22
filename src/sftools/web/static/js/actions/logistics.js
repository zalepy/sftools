// Logistics mode (ticket 033): the settings, edited layouts, belts per edge, and zooming in on a node's side.
import { state } from '../state.js';
import { getNodeData, selectLogistics, getEdgeData } from '../graph.js';
import * as logisticsView from '../logistics.js';
import { nodeLabel } from '../panel/common.js';
import { readLogisticsSettings } from '../panel/planner.js';
import { showEdgeDetails, hideEdgeDetails } from '../panel/selection.js';
import { showToast } from '../panel/messages.js';
import { save, render, requestPlan, recalculate } from './plan.js';

export async function changeLogisticsSettings() {
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

export function zoomIn(nodeId, side, select = null) {
    const node = getNodeData(nodeId);
    if (!node || !node.logistics || !node.logistics[side]) {
        showToast("That end isn't in the plan's logistics: it's the demand, the Sink or inbound production.");
        return;
    }
    logisticsView.openView(node, side, {
        onChange: layout => setLayout(nodeId, side, layout),
        describe: nodeLabel,
        onMove: save,
        onBelts: setEdgeBelts,
        onOpen: zoomIn
    }, select);
}

/**
 * Sets how many belts an edge has (ticket 041); null goes back to the fewest its rate needs. The layouts
 * of both its ends are suggested again (the server resets edited ones, with a notice).
 */
export async function setEdgeBelts(key, count) {
    const edges = { ...state.logistics.edges };
    if (count === null) delete edges[key]; else edges[key] = count;
    try {
        render(await requestPlan({ edges }));
        state.logistics.edges = edges;
        save();
        const edge = getEdgeData(key);
        if (edge) showEdgeDetails(edge); else hideEdgeDetails();
    } catch (e) {
        console.error("Belt change failed", e);
        alert(`Belt change failed: ${e.message}`);
    }
}
