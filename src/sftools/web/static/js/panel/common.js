// Shared by the side panel's modules: element lookup, node names, stat rows, and the Node tab's empty text.
import { getNodeData } from '../graph.js';

export const EPSILON = 0.0001;
export const $ = id => document.getElementById(id);

// The Node tab says what to click while nothing is selected
export function updateNodeEmpty() {
    const shown = ['node-details', 'byproduct-details', 'edge-details', 'logistics-details']
        .some(id => $(id) && $(id).style.display === 'block');
    $('node-empty').hidden = shown;
}

// IDs are item paths ('Smart Plating__Rotor__Screws', see child_node_id): name a consumer by its item
// and the item it feeds, which tells apart several nodes making the same item.

/** A production node by name, as in the input breakdown: e.g. "Screws (in Rotor)". */
export function nodeLabel(nodeId) {
    if (nodeId === 'External Demand') return 'External Demand';
    const raw = getNodeData(nodeId);
    if (!raw) return nodeId;
    if (raw.burn) return `${raw.output_item} (burning residue)`;
    if (raw.generators) return raw.building;
    const path = nodeId.split('__');
    return path.length > 1 ? `${raw.output_item} (in ${path.at(-2)})` : `${raw.output_item} (demand)`;
}

/** One line per step, e.g. "Reinforced Iron Plate ← Alternate: Bolted Iron Plate (Assembler)". */
export function derivationText(derivation) {
    return derivation.map(step => `${step.item} ← ${step.recipe} (${step.building})`).join('\n');
}

export function statRow(label, value, { className = 'stat-row', style = '' } = {}) {
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
