// A reference layout (ticket 056) drawn as SVG markup: no DOM, so it's unit-tested (tests/js/).
// The layout is data (static/layouts/<id>.json) on a grid of squares: belts on the floor first, the pipes
// raised over them, then the buildings and the labels. Hovering anything shows its <title>.

const CELL = 28;
const BELT_WIDTH = 0.8;   // of a square: wider than a pipe, so a pipe over a belt shows the belt either side
const PIPE_WIDTH = 0.45;

export function escapeXml(text) {
    return String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}

const center = v => (v + 0.5) * CELL;
const percent = clock => `${+(clock * 100).toFixed(3)}%`;
const title = text => text ? `<title>${escapeXml(text)}</title>` : '';

function trace(t) {
    const width = (t.kind === 'belt' ? BELT_WIDTH : PIPE_WIDTH) * CELL;
    // A belt is striped (its dashes as the belt's slats), so it has flat ends; a pipe's ends are squared off
    const style = t.kind === 'belt' ? `stroke-linecap="butt" stroke-dasharray="${CELL / 4} ${CELL / 10}"` : 'stroke-linecap="square"';
    const paths = t.paths.map(points => `<polyline points="${points.map(([x, y]) => `${center(x)},${center(y)}`).join(' ')}" `
        + `fill="none" stroke="${t.color}" stroke-width="${width}" stroke-linejoin="miter" ${style}/>`);
    const totals = (t.totals || []).map(([[x, y], value]) => `<text x="${center(x)}" y="${center(y)}" class="layout-total">${value}</text>`);
    return `<g class="layout-trace layout-${t.kind}" data-id="${escapeXml(t.id)}">${title(t.title)}${paths.join('')}${totals.join('')}</g>`;
}

/** What a building does, for its tooltip, e.g. "Refinery 12: Turbofuel, from the green Fuel pipe into the right red Turbofuel pipe". */
export function buildingTitle(building, traces) {
    const pipe = id => {
        const t = traces.find(t => t.id === id) || { name: id };
        return ['the', t.name, t.item, 'pipe'].filter(Boolean).join(' ');
    };
    const clock = building.clock && building.clock !== 1 ? ` at ${percent(building.clock)}` : '';
    const from = building.from ? ` from ${pipe(building.from)}` : '';
    return `Refinery ${building.label}: ${building.recipe}${clock},${from} into ${pipe(building.into)}`;
}

const mw = value => `${Math.round(value).toLocaleString('en')} MW`;

/** What the build itself draws, from its `power` rows, as built (e.g. the Pressurizer at 250%). */
export function powerNote(layout) {
    const rows = layout.power || [];
    if (!rows.length) return '';
    const used = rows.reduce((sum, row) => sum + row.mw, 0);
    const made = (layout.table || []).flatMap(row => row.generators ? row.out : []).reduce((sum, [, rate]) => sum + rate, 0);
    const parts = rows.map(row => `${row.count} ${row.what}${row.clock ? ` at ${percent(row.clock)}` : ''}`
        + `${row.detail ? ` (${row.detail})` : ''} ${mw(row.mw)}`);
    const net = made ? ` of the ${mw(made)} (${mw(made - used)} net)` : '';
    return `Power used: ${mw(used)}${net}: ${parts.join(', ')}. Power grows with clock^1.32: adjust for your own nodes and clocks.`;
}

function building(b, layout) {
    const fill = (layout.recipes || {})[b.recipe] || '#334155';
    // The pipe it's on (Fuel in for Turbofuel, Fuel out for Fuel) colors its edge and number, as in the sheet
    const pipe = layout.traces.find(t => t.id === (b.from || b.into)) || {};
    const color = pipe.color || '#94a3b8';
    const inset = CELL * 0.08;
    return `<g class="layout-building">${title(buildingTitle(b, layout.traces))}`
        + `<rect x="${b.x * CELL + inset}" y="${b.y * CELL + inset}" width="${CELL - 2 * inset}" height="${CELL - 2 * inset}" rx="3" `
        + `fill="${fill}" stroke="${color}" stroke-width="2"/>`
        + `<text x="${center(b.x)}" y="${center(b.y)}" class="layout-label" fill="${color}">${escapeXml(b.label)}</text></g>`;
}

// A label, or with a color a marker: a round badge, e.g. where a pipe dives down to another floor
function label(l) {
    if (!l.color) return `<text x="${center(l.x)}" y="${center(l.y)}" class="layout-note">${title(l.title)}${escapeXml(l.text)}</text>`;
    return `<g class="layout-marker">${title(l.title)}<circle cx="${center(l.x)}" cy="${center(l.y)}" r="${CELL * 0.38}" `
        + `fill="${l.color}" stroke="#0f172a" stroke-width="2"/>`
        + `<text x="${center(l.x)}" y="${center(l.y)}" class="layout-label" fill="#0f172a">${escapeXml(l.text)}</text></g>`;
}

/** The layout's drawing: belts, pipes, buildings, labels, in that order (later ones over earlier). */
export function layoutSvg(layout) {
    const [width, height] = layout.size;
    const traces = layout.traces || [];
    const parts = [
        ...traces.filter(t => t.kind === 'belt').map(trace),
        ...traces.filter(t => t.kind !== 'belt').map(trace),
        ...(layout.buildings || []).map(b => building(b, layout)),
        ...(layout.labels || []).map(label),
    ];
    return `<svg xmlns="http://www.w3.org/2000/svg" class="layout-svg" viewBox="0 0 ${width * CELL} ${height * CELL}" `
        + `width="${width * CELL}" height="${height * CELL}" role="img" aria-label="${escapeXml(layout.title)}">${parts.join('')}</svg>`;
}
