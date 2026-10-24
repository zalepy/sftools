// What a node's data says, as text and colors: no DOM or Cytoscape, so it's unit-tested (tests/js/).
import { state } from './state.js';

const LIGHT_TEXT = '#f8fafc';
const DARK_TEXT = '#0f172a';
const EPSILON = 0.0001;

// WCAG relative luminance of a #rrggbb color
function luminance(hex) {
    const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
    const [r, g, b] = channels.map(c => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Light or dark text, whichever contrasts more with the background. */
export function textColorOn(background) {
    if (!/^#[0-9a-f]{6}$/i.test(background)) return LIGHT_TEXT;
    const bg = luminance(background);
    const contrast = text => (Math.max(bg, text) + 0.05) / (Math.min(bg, text) + 0.05);
    return contrast(luminance(DARK_TEXT)) > contrast(luminance(LIGHT_TEXT)) ? DARK_TEXT : LIGHT_TEXT;
}

/** Whether the user demands this node (or a node merged into it) directly. */
export function isExternalDemand(node) {
    return (node.external_demand || 0) > EPSILON;
}

/** Inbound production per minute that nothing in the plan uses. */
export function inboundUnused(node) {
    return parseFloat(node.inbound.rate) - parseFloat(node.inbound.used);
}

/**
 * Buildings needed and built (ticket 037), or null for nodes without buildings to build (inbound
 * production). Built counts are kept per recipe: after a recipe switch they no
 * longer count, and `stale` holds the old mark.
 */
export function builtStatus(node, built = state.built) {
    if (!node || node.inbound) return null;
    const needed = node.clocks && node.clocks.length ? node.buildings : Math.ceil(parseFloat(node.building_scale) - EPSILON);
    if (!(needed > 0)) return null;
    const mark = built[node.id];
    const current = mark && mark.recipe === node.recipe_name;
    const count = current ? mark.count : 0;
    return { needed, built: count, done: count >= needed, stale: mark && !current ? mark : null };
}

// Small dot in the top-right corner: blue = a whole building or more spare, green = surplus, red = shortage.
// Inbound production has no buildings: green when some of it goes unused.
export function statusColor(node) {
    if (node.inbound) return inboundUnused(node) > EPSILON ? '#22c55e' : null;
    const surplus = parseFloat(node.building_scale) - parseFloat(node.ideal_building_scale);
    if (surplus > 1 - EPSILON) return '#3b82f6';
    if (surplus > EPSILON) return '#22c55e';
    if (surplus < -EPSILON) return '#ef4444';
    return null;
}

/** "10×", or "8 × 100% + 1 × 200%" when any building runs at another clock. */
export function clocksText(node, separator = ' × ') {
    const groups = (node.clocks || []).filter(g => g.count > 0);
    if (groups.length === 0 || groups.every(g => g.clock === 1)) return '';
    return groups.map(g => `${g.count}${separator}${+(g.clock * 100).toFixed(2)}%`).join(' + ');
}

/**
 * Generators (tickets 055, 057): how many, and how many of them the fuel keeps running, e.g.
 * "4× Fuel Generator, 3.33 fed".
 */
export function generatorsText(node) {
    return `${node.buildings}× ${node.building}, ${node.generators.fed.toFixed(2)} fed`;
}

/** What generators burn, and their water: "66.67/min Turbofuel, 20.00/min Fuel burned · 450.00/min Water". */
export function burnedText(node) {
    const { fuels, water } = node.generators;
    const burned = `${fuels.map(f => `${f.rate.toFixed(2)}/min ${f.item}`).join(', ')} burned`;
    return water ? `${burned} · ${water.toFixed(2)}/min Water` : burned;
}

/** Number of buildings: whole with clocks, otherwise the fractional scale. */
export function buildingsText(node) {
    return node.clocks && node.clocks.length ? `${node.buildings}` : parseFloat(node.building_scale).toFixed(2);
}
